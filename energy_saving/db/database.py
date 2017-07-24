"""Provider interface to manipulate database."""
import logging
from oslo_config import cfg
import six

from contextlib import contextmanager
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
    logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
    fine_debug = root_logger.isEnabledFor(loglevel_mapping['fine'])
    if fine_debug:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.DEBUG)
    finest_debug = root_logger.isEnabledFor(
        loglevel_mapping['finest']
    )
    if finest_debug:
        logging.getLogger('sqlalchemy.dialects').setLevel(logging.DEBUG)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
        logging.getLogger('sqlalchemy.orm').setLevel(logging.DEBUG)
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
def influx_session():
    if not INFLUX_SESSION:
        init()
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


def _get_attribute_dict(attribute):
    return {
        'devices': [],
        'attribute': {
            'type': attribute.type,
            'unit': attribute.unit,
            'mean': attribute.mean,
            'deviation': attribute.deviation
        }
    }


def _get_parameter_dict(parameter):
    return {
        'devices': [],
        'attribute': {
            'type': parameter.type,
            'unit': parameter.unit,
            'min': parameter.min,
            'max': parameter.max
        }
    }


def get_sensor_attributes(datacenter):
    result = {}
    for attribute in datacenter.sensor_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.sensor_name)
    return result


def get_controller_attributes(datacenter):
    result = {}
    for attribute in datacenter.controller_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.controller_name)
    return result


def get_power_supply_attributes(datacenter):
    result = {}
    for attribute in datacenter.power_supply_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.power_supply_name)
    return result


def get_controller_power_supply_attributes(datacenter):
    result = {}
    for attribute in datacenter.controller_power_supply_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.controller_power_supply_name)
    return result


def get_environment_sensor_attributes(datacenter):
    result = {}
    for attribute in datacenter.environment_sensor_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.environment_sensor_name)
    return result


def get_controller_parameters(datacenter):
    result = {}
    for parameter in datacenter.controller_parameters:
        result[parameter.name] = _get_parameter_dict(parameter)
        parameter_data = result[parameter.name]['devices']
        for data in parameter.parameter_data:
            parameter_data.append(data.controller_name)
    return result


DEVICE_TYPE_METADATA_GETTERS = {
    'sensor_attribute': get_sensor_attributes,
    'controller_attribute': get_controller_attributes,
    'controller_parameter': get_controller_parameters,
    'power_supply_attribute': get_power_supply_attributes,
    'controller_power_supply_attribute': (
        get_controller_power_supply_attributes
    ),
    'environment_sensor_attribute': get_environment_sensor_attributes
}


def _get_datacenter_device_type_metadata(datacenter, device_type):
    if device_type not in DEVICE_TYPE_METADATA_GETTERS:
        raise exception.RecordNotExists(
            'device type %s does not exist' % device_type
        )
    return DEVICE_TYPE_METADATA_GETTERS[device_type](datacenter)


def get_datacenter_device_type_metadata(
    session, datacenter_name, device_type
):
    datacenter = session.query(
        models.Datacenter
    ).filter_by(name=datacenter_name).first()
    if not datacenter:
        raise exception.RecordNotExists(
            'datacener %s does not exist' % datacenter_name
        )
    device_type_metadata = _get_datacenter_device_type_metadata(
        datacenter, device_type
    )
    logger.debug(
        'datacenter %s device type %s metadata: %s',
        datacenter_name, device_type, device_type_metadata
    )
    return device_type_metadata


def get_device_type_meatadata_from_datacenter_meatadata(
    datacenter_metadata, device_type
):
    return datacenter_metadata['device_types'][device_type]


def _get_datacenter_metadata(datacenter):
    result = {}
    for key, value in six.iteritems(DEVICE_TYPE_METADATA_GETTERS):
        result[key] = value(datacenter)
    return {
        'time_interval': datacenter.time_interval,
        'models': datacenter.models,
        'properties': datacenter.properties,
        'device_types': result
    }


def get_datacenter_metadata(session, datacenter_name):
    datacenter = session.query(
        models.Datacenter
    ).filter_by(name=datacenter_name).first()
    if not datacenter:
        raise exception.RecordNotExists(
            'datacener %s does not exist' % datacenter_name
        )
    datacenter_metadata = _get_datacenter_metadata(datacenter)
    logger.debug(
        'datacenter %s metadata: %s',
        datacenter_name, datacenter_metadata
    )
    return datacenter_metadata


def get_datacenter_metadata_from_metadata(metadata, datacenter_name):
    return metadata[datacenter_name]


def get_metadata(session):
    result = {}
    datacenters = session.query(models.Datacenter)
    for datacenter in datacenters:
        result[datacenter.name] = (
            _get_datacenter_metadata(datacenter)
        )
    return result

TIMESERIES_VALUE_CONVERTERS = {
    'binary': bool,
    'continuous': float,
    'integer': int,
    'discrete': str
}


def convert_timeseries_value(
    value, value_type, raise_exception=False
):
    try:
        return TIMESERIES_VALUE_CONVERTERS[value_type](value)
    except Exception as error:
        if raise_exception:
            raise error
        else:
            return None


TIMESERIES_VALUE_FORMATTERS = {
    'binary': bool,
    'continuous': lambda x: round(x, 2),
    'integer': int,
    'discrete': str
}


def format_timeseries_value(
    value, value_type
):
    return TIMESERIES_VALUE_FORMATTERS[value_type](value)
