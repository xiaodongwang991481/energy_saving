"""celeryconfig wrapper.

   .. moduleauthor:: Xiaodong Wang <xiaodongwang@huawei.com>
"""
import logging
import os.path

from oslo_config import cfg

from energy_saving.utils import settings
from energy_saving.utils import util


logger = logging.getLogger(__name__)
opts = [
    cfg.StrOpt(
        'celeryconfig_dir',
        help='celery config directory',
        default=settings.CELERYCONFIG_DIR
    ),
    cfg.StrOpt(
        'celeryconfig_filename',
        help='celery config filename',
        default=settings.CELERYCONFIG_FILE
    )
]
CONF = util.CONF
CONF.register_cli_opts(opts)


CELERY_RESULT_BACKEND = 'amqp://'

BROKER_PROTOCOL = 'amqp'
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
CELERY_DEFAULT_QUEUE = 'energy_saving'
CELERY_DEFAULT_EXCHANGE = 'energy_saving'
CELERY_DEFAULT_ROUTING_KEY = 'energy_saving'
C_FORCE_ROOT = 1
celeryconfig_file = CONF.celeryconfig_filename
if celeryconfig_file:
    celeryconfig_dir = CONF.celeryconfig_dir
    CELERY_CONFIG = os.path.join(
        celeryconfig_dir,
        celeryconfig_file
    )
    if os.path.exists(CELERY_CONFIG):
        try:
            logger.info('load celery config from %s', CELERY_CONFIG)
            with open(CELERY_CONFIG) as f:
                code = compile(f.read(), CELERY_CONFIG, 'exec')
                exec(code, globals(), locals())
        except Exception as error:
            logger.exception(error)
            raise error
    else:
        logger.error(
            'ignore unexisting celery config file %s', CELERY_CONFIG
        )
