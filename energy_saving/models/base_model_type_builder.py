
import abc
# from abc import abstractmethod
import logging
import os
import os.path
import pandas
import simplejson as json
import six

from oslo_config import cfg

from energy_saving.db import database
from energy_saving.utils import settings
from energy_saving.utils import util


opts = [
    cfg.StrOpt(
        'model_dir',
        help='model directory',
        default=settings.DATA_DIR
    )
]
CONF = util.CONF
CONF.register_cli_opts(opts)
logger = logging.getLogger(__name__)


class BaseModelType(object):
    def __init__(self, datacenter, model_type):
        self.datacenter = datacenter
        self.model_type = model_type
        self.metadata = self.get_metadata()
        self.model = self.load_model()

    def get_model_file(self):
        return os.path.join(
            CONF.model_dirf, self.metadata['models'][self.model_type]
        )

    def load_model(self):
        model_file = self.get_model_file()
        with open(model_file, encoding='utf-8') as data_file:
            return json.loads(data_file.read())

    def _get_dataframe(self, session, queries, query_args):
        dataframe = {}
        inputs = {}
        for query in self.model['input_queries']:
            query = query % query_args
            result = session.query(query, epoch='s')
            for key, value in result.items():
                logger.debug('iterate mesurement %s', key)
                measurement, group_tags = key
                for item in value:
                    item.update(group_tags)
                    device = item['device']
                    device_type = item['device_type']
                    item_key = '%s.%s.%s' % (
                        measurement, device_type, device
                    )
                    timestamp = item['time']
                    key_inputs = inputs.setdefault(item_key, {})
                    key_inputs[timestamp] = item['value']
        for key, value in six.iteritems(inputs):
            times, values = zip(value.items())
            dataframe[key] = pandas.Series(values, index=times)
        return pandas.DataFrame(dataframe)

    def _get_dataframe_from_data(self, data):
        dataframe = {}
        for device_type, device_type_data in six.iteritems(data):
            for measurement, measurement_data in six.iteritems(
                device_type_data
            ):
                for device, device_data in six.iteritems(measurement_data):
                    times, values = zip(device_data.items())
                    key = '%s.%s.%s' % (measurement, device_type, device)
                    dataframe[key] = pandas.Series(values, index=times)
        return pandas.DataFrame(dataframe)

    def get_data(self, starttime, endtime):
        time_interval = self.metadata['time_interval']
        query_args = {
            'time_interval': time_interval,
            'datacenter': self.datacenter,
            'starttime': starttime,
            'endtime': endtime
        }
        input_dataframe = None
        output_dataframe = None
        with database.influx_session() as session:
            if 'input_queries' in self.model:
                input_dataframe = self._get_dataframe(
                    session, self.model['input_queries'], query_args
                )
            if 'output_queries' in self.model:
                output_dataframe = self._get_dataframe(
                    session, self.model['output_queries'], query_args
                )
        return input_dataframe, output_dataframe

    def get_metadata(self):
        with database.session() as session:
            return database.get_datacenter_metadata(
                session, self.datacenter
            )

    def save(self):
        pass

    def build(self):
        pass

    def get_input_and_output(self, data):
        input_dataframe = None
        output_dataframe = None
        if 'input' in data:
            input_dataframe = self._get_dataframe_from_data(data['input'])
        if 'output' in data:
            output_dataframe = self._get_dataframe_from_data(data['output'])
        return input_dataframe, output_dataframe

    def test(self, starttime=None, endtime=None, data=None):
        if not data:
            (
                input_dataframe, output_dataframe
            ) = self.get_input_and_output(data)
        else:
            input_dataframe, output_dataframe = self.get_data(
                starttime=starttime, endtime=endtime
            )

    def train(self, starttime=None, endtime=None, data=None):
        if not data:
            (
                input_dataframe, output_dataframe
            ) = self.get_input_and_output(data)
        else:
            input_dataframe, output_dataframe = self.get_data(
                starttime=starttime, endtime=endtime
            )

    def apply(self, starttime=None, endtime=None, data=None):
        if not data:
            input_dataframe, _ = self.get_input_and_output(data)
        else:
            input_dataframe, _ = self.get_data(
                starttime=starttime, endtime=endtime
            )


class BaseModelTypeBuilder(abc.ABCMeta):
    def __init__(self, *args, **kwargs):
        logger.debug(
            'init %s with args=%s kwargs=%s',
            self.__class__.__name__, args, kwargs
        )
        self.model_types = {}

    def create_model_type(self, datacenter, model_type):
        return BaseModelType(datacenter, model_type)

    def get_model_type(self, datacenter, model_type):
        return self.create_model_type(datacenter, model_type)

    def build(self, datacenter, model_type):
        model_type_class = self.create_model_type(
            datacenter, model_type
        )
        self.model_types[datacenter] = model_type_class
        return model_type_class.build()

    def train(self, datacenter, model_type, **kwargs):
        model_type_class = self.load(datacenter, model_type)
        return model_type_class.train(**kwargs)

    def test(self, datacenter, model_type, test_result, **kwargs):
        model_type_class = self.load(datacenter, model_type)
        return model_type_class.test(**kwargs)

    def apply(self, datacenter, model_type, prediction, **kwargs):
        model_type_class = self.load(datacenter, model_type)
        return model_type_class.apply(**kwargs)

    def save(self, datacenter, model_type):
        model_type_class = self.model_types[datacenter]
        model_type_class.save()
        return model_type_class

    def load(self, datacenter, model_type):
        if datacenter in self.model_types:
            return self.model_types[datacenter]
        model_type_class = self.get_model_type(datacenter, model_type)
        self.model_types[datacenter] = model_type_class
        return model_type_class
