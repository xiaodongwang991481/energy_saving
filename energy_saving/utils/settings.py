# coding=utf-8
import lazypy
import logging
import os
import os.path

# default setting
CONFIG_DIR = os.environ.get('ENERGY_SAVING_CONFIG_DIR', '/etc/energy_saving')

DATABASE_TYPE = 'mysql'
DATABASE_USER = 'root'
DATABASE_PASSWORD = 'root'
DATABASE_IP = '127.0.0.1'
DATABASE_PORT = 3306
DATABASE_SERVER = lazypy.delay(
    lambda: '%s:%s' % (DATABASE_IP, DATABASE_PORT)
)
DATABASE_NAME = 'energy_saving'
DATABASE_URI = lazypy.delay(
    lambda: '%s://%s:%s@%s/%s' % (
        lazypy.force(DATABASE_TYPE),
        lazypy.force(DATABASE_USER),
        lazypy.force(DATABASE_PASSWORD),
        lazypy.force(DATABASE_SERVER),
        lazypy.force(DATABASE_NAME)
    )
)

DATABASE_POOL_TYPE = 'instant'

DEBUG = True
SERVER_PORT = 80
DEFAULT_LOGLEVEL = 'debug'
DEFAULT_LOGDIR = '/var/log/energy_saving'
DEFAULT_LOGINTERVAL = 6
DEFAULT_LOGINTERVAL_UNIT = 'h'
DEFAULT_LOGFORMAT = (
    '%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s')
DEFAULT_LOGBACKUPCOUNT = 5
WEB_LOGFILE = 'web.log'
DB_MANAGE_LOGFILE = 'db_manage.log'
CELERY_LOGFILE = 'celery.log'
CELERYCONFIG_DIR = lazypy.delay(lambda: '%s' % CONFIG_DIR)
CELERYCONFIG_FILE = 'celeryconfig'

WEB_DIR = '/var/www/energy_saving_web'
DATA_DIR = '/opt/energy_saving'

INFLUX_IP = '127.0.0.1'
INFLUX_PORT = 8086
INFLUX_DATABASE = 'energy_saving'
INFLUX_USER = 'root'
INFLUX_PASSWORD = 'root'
INFLUX_SERVER = lazypy.delay(
    lambda: '%s:%s' % (INFLUX_IP, INFLUX_PORT)
)
INFLUX_URI = lazypy.delay(
    lambda: '%s://%s:%s@%s/%s' % (
        'influxdb',
        lazypy.force(INFLUX_USER),
        lazypy.force(INFLUX_PASSWORD),
        lazypy.force(INFLUX_SERVER),
        lazypy.force(INFLUX_DATABASE)
    )
)
INFLUX_TIMEOUT = 5
DEFAULT_TIME_PRECISION = None
DEFAULT_INFLUX_VALUE = ''
IGNORABLE_INFLUX_VALUES = ['', '-']
DEFAULT_EXPORT_TIMESTAMP_COLUMN = 'time'
DEFAULT_EXPORT_DEVICE_COLUMN = 'device'
DEFAULT_EXPORT_MEASUREMENT_COLUMN = ''
DEFAULT_IMPORT_ADD_SECONDS_SAME_TIMESTAMP = 10

if (
    'ENERGY_SAVING_SETTINGS' in os.environ and
    os.environ['ENERGY_SAVING_SETTINGS']
):
    SETTINGS = os.environ['ENERGY_SAVING_SETTINGS']
else:
    SETTINGS = '%s/settings' % CONFIG_DIR
if os.path.exists(SETTINGS):
    try:
        logging.info('load settings from %s', SETTINGS)
        execfile(SETTINGS, globals(), locals())
    except Exception as error:
        logging.exception(error)
        raise error
else:
    logging.error(
        'ignore unexisting setting file %s', SETTINGS
    )


CONFIG_VARS = vars()
for key, value in CONFIG_VARS.items():
    if isinstance(value, lazypy.Promise):
        CONFIG_VARS[key] = lazypy.force(value)
