"""Provider interface to manipulate database."""
import logging
from oslo_config import cfg

from contextlib import contextmanager
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


opts = [
    cfg.StrOpt('database_uri',
               help='database uri',
               default=settings.DATABASE_URI)
]
CONF = cfg.CONF
CONF.register_opts(opts)

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
logger = logging.getLogger(__name__)


def init(database_url=None):
    """Initialize database.

    Adjust sqlalchemy logging if necessary.

    :param database_url: string, database url.
    """
    global ENGINE
    global SCOPED_SESSION
    if not database_url:
        database_url = CONF.database_uri
    logger.info('init database %s', database_url)
    root_logger = logging.getLogger()
    loglevel_mapping = logsetting.LOGLEVEL_MAPPING
    fine_debug = root_logger.isEnabledFor(loglevel_mapping['fine'])
    if fine_debug:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    finest_debug = root_logger.isEnabledFor(
        loglevel_mapping['finest']
    )
    if finest_debug:
        logging.getLogger('sqlalchemy.dialects').setLevel(logging.INFO)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.INFO)
        logging.getLogger('sqlalchemy.orm').setLevel(logging.INFO)
    poolclass = POOL_MAPPING[
        settings.DATABASE_POOL_TYPE
    ]
    ENGINE = create_engine(
        database_url, convert_unicode=True,
        poolclass=poolclass
    )
    SESSION.configure(bind=ENGINE)
    SCOPED_SESSION = scoped_session(SESSION)


def in_session():
    """check if in database session scope."""
    bool(hasattr(SESSION_HOLDER, 'session'))


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
