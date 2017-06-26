"""Module to define celery tasks.

   .. moduleauthor:: Xiaodong Wang <xiaodongwang@huawei.com>
"""
import logging

from celery.signals import celeryd_init
from celery.signals import setup_logging

from oslo_config import cfg

from energy_saving.db import database
from energy_saving.tasks.client import celery
from energy_saving.utils import logsetting
from energy_saving.utils import settings


opts = [
    cfg.StrOpt('logfile',
               help='log file name',
               default=settings.CELERY_LOGFILE)
]
CONF = cfg.CONF
CONF.register_opts(opts)


logger = logging.getLogger(__name__)


@celeryd_init.connect()
def global_celery_init(**_):
    """Initialization code."""
    logsetting.init()
    database.init()


@setup_logging.connect()
def tasks_setup_logging(**_):
    """Setup logging options from orca setting."""
    logsetting.init()


@celery.task(name='energy_saving.tasks.train', ignore_result=False)
def train_model():
    """Deploy the given task services."""
    pass
