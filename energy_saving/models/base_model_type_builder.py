
import abc
# from abc import abstractmethod
import datetime
import logging
import os
import os.path
import pandas as pd
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
            return timeseries.get_datacenter_metadata(
                session, self.datacenter
            )

    def load_nodes(self):
        nodes = self.load_config(self.config['nodes'])
        self.input_nodes = nodes['input']
        self.output_nodes = nodes['output']

    def load_built(self):
        logger.debug('load built? %s', self.built)
        if not self.built:
            self.load_nodes()
            self.built = True
            model_path = self.get_file(self.config['model_path'])
            self.model = self.model_builder.get_model(
                self, model_path,
                [self.get_node_key(node) for node in self.input_nodes],
                [self.get_node_key(node) for node in self.output_nodes]
            )
            logger.debug('built model is loaded')

    def load_trained(self):
        self.load_built()
        logger.debug('load trained? %s', self.trained)
        if not self.trained:
            self.load_model()
            self.trained = True
            logger.debug('trained model is loaded')

    def save_model(self):
        model_config = self.model.save()
        self.save_config(
            self.config['model_config'],
            model_config
        )

    def load_model(self):
        self.model.load()

    def save_nodes(self):
        self.save_config(
            self.config['nodes'],
            {'input': self.input_nodes, 'output': self.output_nodes}
        )

    def save_built(self):
        logger.debug('save built model')
        self.save_nodes()
        self.built = True
        self.trained = False

    def save_trained(self):
        logger.debug('save trained model')
        self.save_model()
        self.trained = True

    def _create_nodes(self, patterns):
        nodes = []
        logger.debug(
            'create nodes with patttern: %s', patterns
        )
        device_type_mapping = timeseries.get_device_type_mapping(
            patterns, self.metadata
        )
        for device_type, measurement_mapping in six.iteritems(
            device_type_mapping
        ):
            device_type_metadata = self.metadata[
                'device_types'
            ][device_type]
            for measurement, devices in six.iteritems(
                measurement_mapping
            ):
                measurement_metadata = device_type_metadata[measurement]
                for device in devices:
                    nodes.append({
                        'device_type': device_type,
                        'measurement':  measurement,
                        'device': device,
                        'unit': measurement_metadata[
                            'attribute'
                        ]['unit'],
                        'type': measurement_metadata[
                            'attribute'
                        ]['type'],
                        'mean': measurement_metadata[
                            'attribute'
                        ]['mean'],
                        'deviation': measurement_metadata[
                            'attribute'
                        ]['deviation']
                    })
        return nodes

    def create_nodes(self, data=None):
        if not data:
            input_nodes = self._create_nodes(self.config['inputs'])
            output_nodes = self._create_nodes(self.config['outputs'])
        else:
            input_nodes, output_nodes = (
                data['input_nodes'], data['output_nodes']
            )
        logger.debug(
            'input nodes before processed: %s', input_nodes
        )
        logger.debug(
            'output nodes before processed: %s', output_nodes
        )
        (
            self.input_nodes, self.output_nodes
        ) = self.process_nodes(input_nodes, output_nodes)
        logger.debug('input nodes: %s', self.input_nodes)
        logger.debug('output nodes: %s', self.output_nodes)

    def build(self, data=None):
        logger.debug('%s build model', self)
        self.create_nodes(data)
        model_path = self.get_file(self.config['model_path'])
        self.model = self.model_builder.get_model(
            self, model_path,
            [self.get_node_key(node) for node in self.input_nodes],
            [self.get_node_key(node) for node in self.output_nodes]
        )
        self.save_built()

    def _shift_data(self, data, period):
        time_interval = self.metadata['time_interval']
        return data.shift(
            period, datetime.timedelta(seconds=time_interval)
        )

    def _differentiate_data(self, data):
        shifted_data = self._shift_data(data, -1)
        return (shifted_data - data).iloc[1:]

    def _get_data_from_timeseries(
            self, session,
            starttime, endtime, nodes
    ):
        time_interval = self.metadata['time_interval']
        device_type_mapping = {}
        device_type_types = {}
        for node in nodes:
            device_type = node['device_type']
            measurement = node['measurement']
            device = node['device']
            measurement_mapping = device_type_mapping.setdefault(
                device_type, {}
            )
            measurement_types = device_type_types.setdefault(device_type, {})
            devices = measurement_mapping.setdefault(measurement, [])
            measurement_types.setdefault(
                measurement, node['type']
            )
            if device not in devices:
                devices.append(device)
        response = timeseries.list_timeseries_internal(
            session, {
                'where': {
                    'starttime': starttime,
                    'endtime': endtime
                },
                'group_by': ['time(%ss)' % time_interval],
                'order_by': ['time'],
                'aggregation': 'mean'
            },
            self.datacenter,
            convert_timestamp=True,
            format_timestamp=False,
            device_type_mapping=device_type_mapping,
            device_type_types=device_type_types
        )
        logger.debug(
            'get data from timeseries %s %s',
            starttime, endtime
        )
        return response

    def _get_data_direct(self, data, nodes):
        dataframe = {}
        expected_data = set()
        for node in nodes:
            device_type = node['device_type']
            measurement = node['measurement']
            device = node['device']
            expected_data.add((device_type, measurement, device))
        for device_type, device_type_data in six.iteritems(data):
            for measurement, measurement_data in six.iteritems(
                device_type_data
            ):
                for device, device_data in six.iteritems(measurement_data):
                    key = (measurement, device_type, device)
                    if key in expected_data:
                        times, values = zip(*device_data.items())
                        dataframe[key] = pd.Series(values, index=times)
        return pd.DataFrame(dataframe)

    def get_data(
        self, starttime=None, endtime=None, data=None,
        get_input=True, get_ouput=True
    ):
        input_nodes = self.get_extended_nodes(self.input_nodes)
        output_nodes = self.get_extended_nodes(self.output_nodes)
        logger.debug('get data input nodes: %s', input_nodes)
        logger.debug('get data output nodes: %s', output_nodes)
        if not data:
            with database.influx_session(dataframe=True) as session:
                if get_input:
                    input_data = self._get_data_from_timeseries(
                        session,
                        starttime, endtime,
                        input_nodes
                    )
                else:
                    input_data = None
                if get_ouput:
                    output_data = self._get_data_from_timeseries(
                        session,
                        starttime, endtime,
                        output_nodes
                    )
                else:
                    output_data = None
        else:
            if get_input:
                input_data = self._get_data_direct(
                    data['input_data'],
                    input_nodes
                )
            else:
                input_data = None
            if get_ouput:
                output_data = self._get_data_direct(
                    data['output_data'],
                    self.output_nodes
                )
            else:
                output_data = None
        if input_data is not None:
            logger.debug('input data columns: %s', input_data.columns)
            logger.debug('input data index: %s', input_data.index)
        if output_data is not None:
            logger.debug('output data columns: %s', output_data.columns)
            logger.debug('output data index: %s', output_data.index)
        return (
            self.process_data(
                input_data, output_data
            )
        )

    def test(self, starttime=None, endtime=None, data=None):
        logger.debug('%s test model', self)
        self.load_trained()
        input_data, output_data = self.get_data(
            starttime=starttime, endtime=endtime, data=data
        )
        result = self.model.test(
            input_data, output_data
        )
        return result

    def is_built(self):
        if not self.built:
            logger.error('%s is not built yet', self)
            raise Exception('%s is not built' % self)

    def is_trained(self):
        self.is_built()
        if not self.trained:
            logger.error('%s is not trained yet', self)
            raise Exception('%s is not trained' % self)

    def process_nodes(self):
        return self.input_nodes, self.output_nodes

    def get_node_mapping(self, nodes):
        node_map = {}
        for node in nodes:
            device_type = node['device_type']
            measurement = node['measurement']
            device = node['device']
            node_map[(device_type, measurement, device)] = node
        return node_map

    def get_extended_nodes(self, nodes):
        extended_nodes = []
        for node in nodes:
            if 'sub_nodes' in node:
                extended_nodes.extend(
                    self.get_extended_nodes(node['sub_nodes'])
                )
            else:
                extended_nodes.append(node)
        return extended_nodes

    def normalize_data_by_node(self, data, node, normalized_data={}):
        node_key = self.get_node_key(node)
        normalized_data[node_key] = (
            data[node_key] - node['mean']
        ) / node['deviation']

    def normalize_data_by_nodes(self, data, nodes):
        normralized_data = {}
        for node in nodes:
            self.normalize_data_by_node(data, node, normralized_data)
        return pd.DataFrame(normralized_data)

    def normalize_data(self, input_data, output_data):
        if input_data is not None:
            input_data = self.normalize_data_by_nodes(
                input_data, self.input_nodes
            )
        if output_data is not None:
            output_data = self.normalize_data_by_nodes(
                output_data, self.output_nodes
            )
        return input_data, output_data

    def denormalize_data_by_node(self, data, node, denormalized_data={}):
        node_key = self.get_node_key(node)
        denormalized_data[node_key] = (
            data[node_key] * (node['deviation'] + 0.1) + node['mean']
        )

    def denormalize_data_by_nodes(self, data, nodes):
        denormalized_data = {}
        for node in nodes:
            self.denormalize_data_by_node(data, node, denormalized_data)
        return pd.DataFrame(denormalized_data)

    def denormalize_data(self, input_data, output_data):
        if input_data is not None:
            input_data = self.denormalize_data_by_nodes(
                input_data, self.input_nodes
            )
        if output_data is not None:
            output_data = self.denormalize_data_by_nodes(
                output_data, self.output_nodes
            )
        return input_data, output_data

    def clean_data(self, input_data, output_data):
        if input_data is not None and output_data is not None:
            total = pd.concat(
                [input_data, output_data], axis=1,
                keys=['input', 'output']
            )
            total = total.dropna()
            input_data = total['input']
            output_data = total['output']
        elif input_data is not None:
            input_data = input_data.dropna()
        elif output_data is not None:
            output_data = output_data.dropna()
        return input_data, output_data

    def merge_data_by_nodes(self, data, nodes):
        merged_data = {}
        for node in nodes:
            self.merge_data_by_node(data, node, merged_data)
        return pd.DataFrame(merged_data)

    def get_node_key(self, node):
        device_type = node['device_type']
        measurement = node['measurement']
        device = node['device']
        return (device_type, measurement, device)

    def merge_data_by_node(self, data, node, merged_data={}):
        node_key = self.get_node_key(node)
        node_data = None
        if 'sub_nodes' in node:
            sub_node_dataframe = {}
            for sub_node in node['sub_nodes']:
                sub_node_key = self.get_node_key(sub_node)
                sub_node_dataframe[sub_node_key] = data[sub_node_key]
            node_data = pd.DataFrame(
                sub_node_dataframe
            ).sum(axis=1)
        else:
            node_data = data[node_key]
        merged_data[node_key] = node_data

    def merge_data(self, input_data, output_data):
        if input_data is not None:
            input_data = self.merge_data_by_nodes(
                input_data, self.input_nodes
            )
        if output_data is not None:
            output_data = self.merge_data_by_nodes(
                output_data, self.output_nodes
            )
        return input_data, output_data

    def process_data(self, input_data, output_data):
        input_data, output_data = self.clean_data(
            input_data, output_data
        )
        input_data, output_data = self.merge_data(
            input_data, output_data
        )
        input_data, output_data = self.normalize_data(
            input_data, output_data
        )
        return input_data, output_data

    def train(self, starttime=None, endtime=None, data=None):
        logger.debug('%s train model', self)
        self.load_built()
        input_data, output_data = self.get_data(
            starttime=starttime, endtime=endtime, data=data
        )
        result = self.model.train(
            input_data, output_data
        )
        self.save_trained()
        return result

    def apply(self, starttime=None, endtime=None, data=None):
        logger.debug('%s apply model', self)
        self.load_trained()
        input_data, _ = self.get_data(
            starttime=starttime, endtime=endtime, data=data,
            get_output=False
        )
        result = self.model.apply(
            input_data
        )
        return result

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
