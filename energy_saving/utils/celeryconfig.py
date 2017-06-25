"""celeryconfig wrapper.

   .. moduleauthor:: Xiaodong Wang <xiaodongwang@huawei.com>
"""
import logging
import os.path

from enrgy_saving.utils import logsetting
from energy_saving.utils import settings


CELERY_RESULT_BACKEND = 'amqp://'

BROKER_PROTOCOL = 'amqp'
DEFAULT_BROKER_USER = 'guest'
BROKER_USER = 'guest'
BROKER_PASSWORD = 'guest'
BROKER_HOST = 'rabbitmq'
BROKER_PORT = 5672
BROKER_ADDR = '%s:%s' % (BROKER_HOST, BROKER_PORT)
BROKER_URL = '%s://%s:%s@%s//' % (
    BROKER_PROTOCOL,
    BROKER_USER,
    BROKER_PASSWORD,
    BROKER_ADDR
)

CELERY_IMPORTS = ('energy_saving.tasks.tasks',)

CELERY_ACCEPT_CONTENT = ['pickle', 'json', 'msgpack', 'yaml']
CELERY_CREATE_MISSING_QUEUES = True
CELERY_DEFAULT_QUEUE = 'deploy'
CELERY_DEFAULT_EXCHANGE = 'deploy'
CELERY_DEFAULT_ROUTING_KEY = 'deploy'
C_FORCE_ROOT = 1
celeryconfig_file = util.parse(setting.CELERYCONFIG_FILE)
if celeryconfig_file:
    celeryconfig_dir = util.parse(setting.CELERYCONFIG_DIR)
    CELERY_CONFIG = os.path.join(
        celeryconfig_dir,
        celeryconfig_file
    )
    if os.path.exists(CELERY_CONFIG):
        try:
            logging.info('load celery config from %s', CELERY_CONFIG)
            execfile(CELERY_CONFIG, globals(), locals())
        except Exception as error:
            logging.exception(error)
            raise error
    else:
        logging.error(
            'ignore unexisting celery config file %s', CELERY_CONFIG
        )

BROKER_PASSWORD = util.parse(BROKER_PASSWORD)
BROKER_ADDR = util.parse(BROKER_ADDR)
BROKER_URL = util.parse(BROKER_URL)
