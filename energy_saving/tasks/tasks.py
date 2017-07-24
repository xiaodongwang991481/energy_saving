"""Module to define celery tasks.

   .. moduleauthor:: Xiaodong Wang <xiaodongwang@huawei.com>
"""
import logging

from celery.signals import celeryd_init
from celery.signals import setup_logging

from oslo_config import cfg

from energy_saving.db import database
from energy_saving.models import model_type_builder_manager
from energy_saving.tasks.client import celery
from energy_saving.utils import logsetting
from energy_saving.utils import settings
from energy_saving.utils import util


opts = [
    cfg.StrOpt('logfile',
               help='log file name',
               default=settings.CELERY_LOGFILE)
]
CONF = util.CONF
CONF.register_cli_opts(opts)


logger = logging.getLogger(__name__)
manager = model_type_builder_manager.ModelTypeBuilderManager()


@celeryd_init.connect()
def global_celery_init(**_):
    """Initialization code."""
    util.init([])
    logsetting.init(CONF.logfile)
    database.init()


@setup_logging.connect()
def tasks_setup_logging(**_):
    """Setup logging options from energy saving setting."""
    pass


@celery.task(name='energy_saving.tasks.build_model')
def build_model(datacenter, model_type):
    """build machine learning model for datacenter."""
    logger.debug('build model %s for %s', model_type, datacenter)
    manager.get_model_type_builder(model_type).build(
        datacenter, model_type
    )


@celery.task(name='energy_saving.tasks.train_model')
def train_model(
    datacenter, model_type, starttime=None, endtime=None,
    data=None
):
    """train machine learning model for datacenter."""
    logger.debug('train model %s for %s', model_type, datacenter)
    manager.get_model_type_builder(model_type).train(
        datacenter, model_type, starttime=starttime,
        endtime=endtime, data=data
    )


@celery.task(name='energy_saving.tasks.test_model')
def test_model(
    datacenter, model_type, test_result,
    starttime=None, endtime=None, data=None
):
    """test machine learning model for datacenter."""
    logger.debug(
        'test model %s for %s in result %s',
        model_type, datacenter, test_result
    )
    manager.get_model_type_builder(model_type).test(
        datacenter, model_type, test_result, starttime=starttime,
        endtime=endtime, data=data
    )


@celery.task(name='energy_saving.tasks.apply_model')
def apply_model(
    datacenter, model_type, prediction,
    starttime=None, endtime=None, data=None
):
    """apply machine learning model for datacenter."""
    logger.debug(
        'apply model %s for %s in prediction %s',
        model_type, datacenter, prediction, prediction
    )
    manager.get_model_type_builder(model_type).apply(
        datacenter, model_type, prediction, starttime=starttime,
        endtime=endtime, data=data
    )
