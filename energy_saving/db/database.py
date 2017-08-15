"""Provider interface to manipulate database."""
import logging
from oslo_config import cfg

from contextlib import contextmanager
from influxdb import DataFrameClient
from influxdb import InfluxDBClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.pool import QueuePool
from sqlalchemy.pool import SingletonThreadPool
from sqlalchemy.pool import StaticPool
from sqlalchemy_utils import create_database
from sqlalchemy_utils import database_exists
from threading import local

from energy_saving.db import exception
from energy_saving.db import models
from energy_saving.utils import logsetting
from energy_saving.utils import settings
from energy_saving.utils import util


opts = [
    cfg.StrOpt(
        'database_uri',
        help='database uri',
        default=settings.DATABASE_URI
    ),
    cfg.StrOpt(
        'database_pool_type',
        help='database pool type',
        default=settings.DATABASE_POOL_TYPE
    ),
    cfg.StrOpt(
        'influx_uri',
        help='influx uri',
        default=settings.INFLUX_URI
    ),
    cfg.IntOpt(
        'influx_timeout',
        help='influx timeout',
        default=settings.INFLUX_TIMEOUT
    )
]
CONF = util.CONF
CONF.register_cli_opts(opts)

ENGINE = None
SESSION = sessionmaker(autocommit=False, autoflush=False)
SCOPED_SESSION = None
SESSION_HOLDER = local()
POOL_MAPPING = {
    'instant': NullPool,
    'static': StaticPool,
    'queued': QueuePool,
    'thread_single': SingletonThreadPool
}
INFLUX_SESSION = None
logger = logging.getLogger(__name__)


class InfluxSession(object):
    def __init__(self, influx_url, timeout=None):
        self.influx_url = influx_url
        self.timeout = timeout

    def get_client(self):
        return InfluxDBClient.from_DSN(
            self.influx_url, timeout=self.timeout
        )

    def get_dataframe_client(self):
        return DataFrameClient.from_DSN(
            self.influx_url, timeout=self.timeout
        )


def is_dataframe_session(session):
    return isinstance(session, DataFrameClient)


def init(database_url=None, influx_url=None):
    """Initialize database.

    Adjust sqlalchemy logging if necessary.

    :param database_url: string, database url.
    """
    global ENGINE
    global SCOPED_SESSION
    global INFLUX_SESSION
    if not database_url:
        database_url = CONF.database_uri
    if not influx_url:
        influx_url = CONF.influx_uri
    influx_timeout = CONF.influx_timeout
    logger.info('init database %s', database_url)
    logger.info('init influx %s', influx_url)
    root_logger = logging.getLogger()
    loglevel_mapping = logsetting.LOGLEVEL_MAPPING
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
    fine_debug = root_logger.isEnabledFor(loglevel_mapping['fine'])
    if fine_debug:
        logging.getLogger('sqlalchemy').setLevel(logging.INFO)
        logging.getLogger('urllib3').setLevel(logging.INFO)
    finest_debug = root_logger.isEnabledFor(
        loglevel_mapping['finest']
    )
    if finest_debug:
        logging.getLogger('sqlalchemy').setLevel(logging.DEBUG)
        logging.getLogger('urllib3').setLevel(logging.DEBUG)
    poolclass = POOL_MAPPING[
        CONF.database_pool_type
    ]
    ENGINE = create_engine(
        database_url, convert_unicode=True,
        poolclass=poolclass
    )
    SESSION.configure(bind=ENGINE)
    SCOPED_SESSION = scoped_session(SESSION)
    INFLUX_SESSION = InfluxSession(influx_url, influx_timeout)


def in_session():
    """check if in database session scope."""
    bool(hasattr(SESSION_HOLDER, 'session'))


@contextmanager
def influx_session(dataframe=False):
    if not INFLUX_SESSION:
        init()
    if dataframe:
        client = INFLUX_SESSION.get_dataframe_client()
    else:
        client = INFLUX_SESSION.get_client()
    logger.debug('influx session %s enter', client)
    try:
        yield client
    except Exception as error:
        logger.exception(error)
        raise exception.DatabaseException(str(error))
    finally:
        logger.debug('influx session %s exit', client)


@contextmanager
def session(exception_when_in_session=True):
    """database session scope.

    To operate database, it should be called in database session.
    If not exception_when_in_session, the with session statement support
    nested session and only the out most session commit/rollback the
    transaction.
    """
    if not ENGINE:
        init()

    nested_session = False
    if hasattr(SESSION_HOLDER, 'session'):
        if exception_when_in_session:
            logger.error('we are already in session')
            raise exception.DatabaseException('session already exist')
        else:
            import traceback
            logger.debug(
                'traceback: %s',
                '\n'.join(traceback.format_stack())
            )
            new_session = SESSION_HOLDER.session
            nested_session = True
            logger.log(
                logsetting.getLevelByName('fine'),
                'reuse session %s', nested_session
            )
    else:
        new_session = SCOPED_SESSION()
        setattr(SESSION_HOLDER, 'session', new_session)
        logger.log(
            logsetting.getLevelByName('fine'),
            'enter session %s', new_session
        )
    try:
        yield new_session
        if not nested_session:
            new_session.commit()
    except Exception as error:
        if not nested_session:
            new_session.rollback()
            logger.error('failed to commit session')
        logger.exception(error)
        if isinstance(error, IntegrityError):
            for item in error.statement.split():
                if item.islower():
                    object = item
                    break
            raise exception.DuplicatedRecord(
                '%s in %s' % (error.orig, object)
            )
        elif isinstance(error, OperationalError):
            raise exception.DatabaseException(
                'operation error in database'
            )
        elif isinstance(error, exception.DatabaseException):
            raise error
        else:
            raise exception.DatabaseException(str(error))
    finally:
        if not nested_session:
            new_session.close()
            SCOPED_SESSION.remove()
            delattr(SESSION_HOLDER, 'session')
        logger.log(
            logsetting.getLevelByName('fine'),
            'exit session %s', new_session
        )


def current_session():
    """Get the current session scope when it is called.

       :return: database session.
       :raises: DatabaseException when it is not in session.
    """
    try:
        return SESSION_HOLDER.session
    except Exception as error:
        logger.error('It is not in the session scope')
        logger.exception(error)
        if isinstance(error, exception.DatabaseException):
            raise error
        else:
            raise exception.DatabaseException(str(error))


def create_db():
    """Create database."""
    if not database_exists(ENGINE.url):
        create_database(ENGINE.url)
    models.BASE.metadata.create_all(bind=ENGINE)


def drop_db():
    """Drop database."""
    models.BASE.metadata.drop_all(bind=ENGINE)
