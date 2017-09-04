"""Module to define celery tasks.

   .. moduleauthor:: Xiaodong Wang <xiaodongwang@huawei.com>
"""
import logging
import six

from celery.signals import celeryd_init
from celery.signals import setup_logging

from oslo_config import cfg

from energy_saving.db import database
from energy_saving.db import models
from energy_saving.db import timeseries
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
manager = model_type_builder_manager.manager


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
def build_model(datacenter, model_type, test_result, data=None):
    """build machine learning model for datacenter."""
    logger.debug(
        'build model %s for %s in result %s',
        model_type, datacenter, test_result
    )
    update_test_result_status(datacenter, test_result, 'pending')
    try:
        model_type_builder = manager.get_model_type_builder(model_type)
        model_type_class = model_type_builder.get_model_type(datacenter)
        model_type_class.build(
            data=data
        )
        update_test_result_status(datacenter, test_result, 'success')
    except Exception as error:
        logger.exception(error)
        update_test_result_status(datacenter, test_result, 'failure')


def update_test_result_status(datacenter, test_result, status):
    logger.debug(
        'update %s test result %s status %s',
        datacenter, test_result, status
    )
    with database.session() as session:
        test_result_db = session.query(
            models.TestResult
        ).filter_by(
            datacenter_name=datacenter, name=test_result
        ).first()
        if not test_result_db:
            datacenter_db = session.query(
                models.Datacenter
            ).filter_by(name=datacenter).first()
            test_result_db = models.TestResult(name=test_result)
            datacenter_db.test_results.append(test_result_db)
        test_result_db.status = status


def save_test_result(datacenter, test_result, result):
    logger.debug('save %s test result %s', datacenter, test_result)
    device_type_mapping = result.get('device_type_mapping', {})
    device_type_types = result.get('device_type_types', {})
    statistics = result.get('statistics', {})
    model = result.get('model')
    model_type = result.get('model_type')
    with database.influx_session(dataframe=True) as session:
        if 'predictions' in result:
            predictions = result['predictions']
            logger.debug('save predictions %s', predictions.columns)
            timeseries.create_test_result_timeseries(
                session, predictions, {
                    'datacenter': datacenter,
                    'reference': test_result
                }, 'prediction',
                device_type_mapping=device_type_mapping,
                device_type_types=device_type_types
            )
        if 'expectations' in result:
            expectations = result['expectations']
            logger.debug('save expectations: %s', expectations.columns)
            timeseries.create_test_result_timeseries(
                session, expectations, {
                    'datacenter': datacenter,
                    'reference': test_result
                }, 'expectation',
                device_type_mapping=device_type_mapping,
                device_type_types=device_type_types
            )
    with database.session() as session:
        logger.debug('save statistics: %s', statistics)
        properties = {
            'device_type_mapping': device_type_mapping,
            'device_type_types': device_type_types,
            'statistics': {
                '.'.join(column): value
                for column, value in six.iteritems(statistics)
            },
            'model': model,
            'model_type': model_type
        }
        test_result_db = session.query(
            models.TestResult
        ).filter_by(
            datacenter_name=datacenter, name=test_result
        ).first()
        if not test_result_db:
            datacenter_db = session.query(
                models.Datacenter
            ).filter_by(name=datacenter).first()
            test_result_db = models.TestResult(name=test_result)
            datacenter_db.test_results.append(test_result_db)
        test_result_db.properties = properties


@celery.task(name='energy_saving.tasks.train_model')
def train_model(
    datacenter, model_type, test_result,
    starttime=None, endtime=None,
    data=None
):
    """train machine learning model for datacenter."""
    logger.debug(
        'train model %s for %s in result %s',
        model_type, datacenter, test_result
    )
    update_test_result_status(datacenter, test_result, 'pending')
    try:
        model_type_builder = manager.get_model_type_builder(model_type)
        model_type_class = model_type_builder.get_model_type(datacenter)
        result = model_type_class.train(
            starttime=starttime,
            endtime=endtime, data=data
        )
        save_test_result(datacenter, test_result, result)
        update_test_result_status(datacenter, test_result, 'success')
    except Exception as error:
        logger.exception(error)
        update_test_result_status(datacenter, test_result, 'failure')


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
    update_test_result_status(datacenter, test_result, 'pending')
    try:
        model_type_builder = manager.get_model_type_builder(model_type)
        model_type_class = model_type_builder.get_model_type(datacenter)
        result = model_type_class.test(
            starttime=starttime,
            endtime=endtime, data=data
        )
        save_test_result(datacenter, test_result, result)
        update_test_result_status(datacenter, test_result, 'success')
    except Exception as error:
        logger.exception(error)
        update_test_result_status(datacenter, test_result, 'failure')


@celery.task(name='energy_saving.tasks.apply_model')
def apply_model(
    datacenter, model_type, test_result,
    starttime=None, endtime=None, data=None
):
    """apply machine learning model for datacenter."""
    logger.debug(
        'apply model %s for %s in test_result %s',
        model_type, datacenter, test_result
    )
    update_test_result_status(datacenter, test_result, 'pending')
    try:
        model_type_builder = manager.get_model_type_builder(model_type)
        model_type = model_type_builder.get_model_type(datacenter)
        result = model_type.apply(
            starttime=starttime,
            endtime=endtime, data=data
        )
        save_test_result(
            datacenter, test_result, {
                'predictions': result,
                'device_type_types': (
                    model_type.generate_device_type_types_by_nodes(
                        model_type.original_output_nodes
                    )
                ),
                'device_type_types': (
                    model_type.generate_device_type_types_by_nodes(
                        model_type.original_output_nodes
                    )
                ),
                'model_type': model_type.builder.name,
                'model': model_type.model_builder.name
            }
        )
        update_test_result_status(datacenter, test_result, 'success')
    except Exception as error:
        logger.exception(error)
        update_test_result_status(datacenter, test_result, 'failure')
