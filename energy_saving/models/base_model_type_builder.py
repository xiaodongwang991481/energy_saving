
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
from energy_saving.db import timeseries
from energy_saving.models import model_builder_manager
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
manager = model_builder_manager.ModelBuilderManager()


class BaseModelType(object):
    def __init__(self, datacenter, builder):
        self.datacenter = datacenter
        self.builder = builder
        self.metadata = self.get_metadata()
        self.config = self.load_config(
            self.metadata['models'].get(
                self.builder.name, '%s.json' % self.builder.name
            )
        )
        logger.debug(
            'model type %s config: %s',
            self.builder.name, self.config
        )
        self.model_builder = self.get_model_builder()
        self.model = self.model_builder.get_model(self)
        self.built = False
        self.trained = False

    def get_model_builder(self):
        return manager.get_model_builder(self.config['model'])

    def get_file(self, filename):
        return os.path.join(
            CONF.model_dir, filename
        )

    def load_config(self, filename):
        config_file = self.get_file(
            filename
        )
        with open(config_file, 'r') as data_file:
            return json.loads(
                data_file.read().decode('utf-8'), encoding='utf-8'
            )

    def save_config(self, filename, data):
        config_file = self.get_file(
            filename
        )
        with open(config_file, 'w') as data_file:
            data_file.write(json.dumps(
                data, ensure_ascii=False, indent=4, encoding='utf-8'
            ).encode('utf-8'))

    def get_metadata(self):
        with database.session() as session:
            return database.get_datacenter_metadata(
                session, self.datacenter
            )

    def load_nodes(self):
        nodes = self.load_config(self.config['nodes'])
        self.input_nodes = nodes['input']
        self.output_nodes = nodes['output']

    def load_built(self):
        if not self.built:
            self.load_nodes()
            self.built = True

    def load_trained(self):
        self.load_built()
        if not self.trained:
            self.load_model()
            self.trained = True

    def save_model(self):
        self.model.save()

    def load_model(self):
        self.model.load()

    def save_nodes(self):
        self.save_config(
            self.config['nodes'],
            {'input': self.input_nodes, 'output': self.output_nodes}
        )

    def save_built(self):
        self.save_nodes()

    def save_trained(self):
        self.save_model()

    def _create_nodes(self, patterns):
        nodes = []
        for pattern in patterns:
            device_types = pattern['device_type']
            if isinstance(device_types, basestring):
                device_types = [device_types]
            measurements = pattern['measurement']
            if isinstance(measurements, basestring):
                measurements = [measurements]
            for device_type in device_types:
                device_type_metadata = self.metadata[
                    'device_types'
                ][device_type]
                for measurement in measurements:
                    measurement_metadata = device_type_metadata[measurement]
                    for device in measurement_metadata['devices']:
                        nodes.append({
                            'device_type': device_type,
                            'measurement':  measurement,
                            'device': device
                        })
        return nodes

    def create_nodes(self, data=None):
        if not data:
            self.input_nodes = self.process_input_nodes(
                self._create_nodes(self.config['inputs'])
            )
            self.output_nodes = self.process_output_nodes(
                self._create_nodes(self.config['outputs'])
            )
        else:
            self.input_nodes = data['input_nodes']
            self.output_nodes = data['output_nodes']

    def build(self, data=None):
        logger.debug('%s build model', self)
        self.create_nodes(data)
        self.model.build()
        self.built = True
        self.save_built()

    def _get_data_from_timeseries(
            self, session,
            starttime, endtime, nodes
    ):
        time_interval = self.metadata['time_interval']
        device_type_mapping = {}
        device_type_types = {}
        device_type_patterns = {}
        for node in nodes:
            device_type = node['device_type']
            measurement = node['measurement']
            device = node['device']
            assert device_type in self.metadata['device_types']
            device_type_metadata = self.metadata['device_types'][device_type]
            assert measurement in device_type_metadata
            measurement_metadata = device_type_metadata[measurement]
            assert device in measurement_metadata['devices']
            measurement_mapping = device_type_mapping.setdefault(
                device_type, {}
            )
            measurement_types = device_type_types.setdefault(device_type, {})
            devices = measurement_mapping.setdefault(measurement, [])
            measurement_types.setdefault(
                measurement, measurement_metadata[
                    'attribute'
                ]['type']
            )
            measurement_patterns = device_type_patterns.setdefault(
                device_type, {}
            )
            measurement_pattern = measurement_metadata['attribute']['pattern']
            if measurement_pattern:
                measurement_patterns.setdefault(
                    measurement, measurement_pattern
                )
            if device not in devices:
                devices.append(device)
        with database.influx_session(dataframe=True) as session:
            response = timeseries.list_timeseries(
                session, {
                    'where': {
                        'datacenter': self.datacenter,
                        'starttime': starttime,
                        'endtime': endtime
                    },
                    'group_by': ['time(%ss)' % time_interval, 'device'],
                    'order_by': ['time', 'device'],
                    'aggregation': 'mean',
                    'device_type': device_type_mapping
                }, device_type_types=device_type_types,
                convert_timestamp=True,
                device_type_patterns=device_type_patterns
            )
        return response

    def _get_data_direct(self, data, nodes):
        dataframe = {}
        for device_type, device_type_data in six.iteritems(data):
            for measurement, measurement_data in six.iteritems(
                device_type_data
            ):
                for device, device_data in six.iteritems(measurement_data):
                    times, values = zip(*device_data.items())
                    key = (measurement, device_type, device)
                    dataframe[key] = pandas.Series(values, index=times)
        return pandas.DataFrame(dataframe)

    def get_data(self, starttime=None, endtime=None, data=None):
        if not data:
            with database.influx_session(dataframe=True) as session:
                input_data = self.process_input_data(
                    self._get_data_from_timeseries(
                        session, self.input_query_template,
                        starttime, endtime,
                        self.input_nodes
                    )
                )
                output_data = self.process_output_data(
                    self._get_data_from_timeseries(
                        session, self.output_query_template,
                        starttime, endtime,
                        self.output_nodes
                    )
                )
        else:
            input_data = self._get_data_direct(
                data['input_data']
            )
            output_data = self._get_data_direct(
                data['output_data']
            )
        return (
            self.process_input_data(input_data),
            self.process_output_data(output_data)
        )

    def test(self, test_result, starttime=None, endtime=None, data=None):
        logger.debug('%s test model', self)
        self.load_trained()
        input_data, output_data = self.get_data(
            starttime=starttime, endtime=endtime, data=data
        )
        self.model.test(input_data, output_data)

    def is_built(self):
        if not self.built:
            logger.error('%s is not built yet', self)
            raise Exception('%s is not built' % self)

    def is_trained(self):
        self.is_built()
        if not self.trained:
            logger.error('%s is not trained yet', self)
            raise Exception('%s is not trained' % self)

    def process_input_nodes(self, input_nodes):
        return input_nodes

    def process_output_nodes(self, output_nodes):
        return output_nodes

    def process_input_data(self, input_data):
        return input_data

    def process_output_data(self, output_data):
        return output_data

    def train(self, starttime=None, endtime=None, data=None):
        logger.debug('%s train model', self)
        self.load_built()
        self.trained = True
        input_data, output_data = self.get_data(
            starttime=starttime, endtime=endtime, data=data
        )
        self.model.train(input_data, output_data)
        self.save_trained()

    def apply(self, prediction, starttime=None, endtime=None, data=None):
        logger.debug('%s apply model', self)
        self.load_trained()

    def __str__(self):
        return '%s[builder=%s, datacenter=%s]' % (
            self.__class__.__name__, self.builder, self.datacenter
        )


@six.add_metaclass(abc.ABCMeta)
class BaseModelTypeBuilder(object):
    def __init__(self, name, *args, **kwargs):
        logger.debug(
            'init %s with args=%s kwargs=%s',
            name, args, kwargs
        )
        self.name = name
        self.model_types = {}

    def create_model_type(self, datacenter):
        return BaseModelType(datacenter, self)

    def get_model_type(self, datacenter):
        if datacenter not in self.model_types:
            self.model_types[datacenter] = self.create_model_type(
                datacenter
            )
        return self.model_types[datacenter]

    def __str__(self):
        return '%s[name=%s]' % (self.__class__.__name__, self.name)
