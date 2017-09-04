import abc
# from abc import abstractmethod
import datetime
import logging
import os
import os.path
import pandas as pd
import shutil
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
manager = model_builder_manager.manager


class BaseModelType(object):
    def __init__(self, datacenter, builder):
        self.SUB_NODES_AGGREGATORS = {
            'sum': self.sum_sub_nodes_data,
            'default': self.sum_sub_nodes_data
        }
        self.NODE_TRANSFORMERS = {
            'shift': self.shift_data,
            'default': self.shift_data
        }
        self.NODE_DETRANSFORMERS = {
            'unshift': self.unshift_data,
            'default': self.unshift_data
        }
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
        self.built = False
        self.trained = False
        self.model_path = None
        self.try_load_built()
        if self.built:
            self.try_load_trained()

    def try_load_built(self):
        if not self.is_built():
            try:
                self.load_built()
            except Exception:
                logger.error('failed to load built')

    def try_load_trained(self):
        if not self.is_trained():
            try:
                self.load_trained()
            except Exception:
                logger.error('failed to load trained')

    def sum_sub_nodes_data(self, data):
        return data.sum(axis=1, skipna=False)

    def get_sub_nodes_aggregator(self, aggregator_name):
        return self.SUB_NODES_AGGREGATORS.get(
            aggregator_name, self.SUB_NODES_AGGREGATORS['default']
        )

    def shift_data(self, data):
        time_interval = self.metadata['time_interval']
        return data.shift(
            -1, datetime.timedelta(seconds=time_interval)
        ).iloc[1:]

    def unshift_data(self, data):
        time_interval = self.metadata['time_interval']
        return data.shift(
            1, datetime.timedelta(seconds=time_interval)
        ).iloc[:-1]

    def get_node_transformer(self, transformer_name):
        return self.NODE_TRANSFORMERS.get(
            transformer_name, self.NODE_TRANSFORMERS['default']
        )

    def get_node_detransformer(self, detransformer_name):
        return self.NODE_DETRANSFORMERS.get(
            detransformer_name, self.NODE_DETRANSFORMERS['default']
        )

    def get_model_builder(self):
        return manager.get_model_builder(self.config['model'])

    def get_file(self, filename):
        return os.path.join(
            CONF.model_dir, filename
        )

    def config_exists(self, filename):
        config_file = self.get_file(
            filename
        )
        return os.path.exists(config_file)

    def load_config(self, filename, raise_exception=True, default=None):
        config_file = self.get_file(
            filename
        )
        if os.path.exists(config_file):
            with open(config_file, 'rb') as data_file:
                return json.loads(
                    data_file.read().decode('utf-8'), encoding='utf-8'
                )
        else:
            if raise_exception:
                raise Exception('file %s is not found' % config_file)
            return default

    def save_config(self, filename, data):
        config_file = self.get_file(
            filename
        )
        with open(config_file, 'wb') as data_file:
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
        self.initialize_nodes_relationship()

    def load_built(self, force=False):
        built = self.is_built()
        logger.debug('load built? %s', built)
        if force or not built:
            self.load_nodes()
            self.create_model()
            logger.debug('built model is loaded')

    def load_trained(self, force=False):
        trained = self.is_trained()
        logger.debug('load trained? %s', trained)
        if force or not trained:
            self.load_model()
            logger.debug('trained model is loaded')

    def save_model(self):
        model_export = self.model.save()
        self.save_config(
            self.config['model_export'],
            model_export
        )

    def load_model(self):
        model_export = self.load_config(
            self.config['model_export']
        )
        self.model.load(model_export)

    def save_nodes(self):
        self.save_config(
            self.config['nodes'],
            {'input': self.input_nodes, 'output': self.output_nodes}
        )

    def save_built(self):
        logger.debug('save built model')
        self.clear_trained()
        self.save_nodes()
        self.set_built()

    def save_trained(self):
        logger.debug('save trained model')
        self.save_model()
        self.set_trained()

    def create_nodes_by_pattern(self, patterns):
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
                        ]['deviation'],
                        'differentiation_mean': measurement_metadata[
                            'attribute'
                        ]['differentiation_mean'],
                        'differentiation_deviation': measurement_metadata[
                            'attribute'
                        ]['differentiation_deviation']
                    })
        return nodes

    def initialize_nodes_relationship(self):
        (
            self.original_input_nodes,
            self.original_output_nodes
        ) = self.generate_original_nodes()
        logger.debug(
            'original input nodes: %s', self.original_input_nodes
        )
        logger.debug(
            'original output nodes: %s', self.original_output_nodes
        )
        (
            self.unmerged_input_nodes,
            self.unmerged_output_nodes
        ) = self.generate_unmerged_nodes()
        logger.debug(
            'unmerged input nodes: %s', self.unmerged_input_nodes
        )
        logger.debug(
            'unmerged output nodes: %s', self.unmerged_output_nodes
        )

    def create_input_nodes(self, pattern=None, data=None):
        if data is None:
            input_nodes = self.create_nodes_by_pattern(pattern)
        else:
            input_nodes = data
        return input_nodes

    def create_output_nodes(self, pattern=None, data=None):
        if data is None:
            output_nodes = self.create_nodes_by_pattern(pattern)
        else:
            output_nodes = data
        return output_nodes

    def create_unmerged_nodes(self, config, data=None):
        return (
            self.create_input_nodes(
                config['inputs'], data.get('input_nodes')
            ),
            self.create_output_nodes(
                config['outputs'], data.get('output_nodes')
            )
        )

    def create_nodes(self, data=None):
        input_nodes, output_nodes = self.create_unmerged_nodes(
            self.config, data or {},
        )
        logger.debug(
            'input nodes: %s', input_nodes
        )
        logger.debug(
            'output nodes: %s', output_nodes
        )
        input_nodes, output_nodes = self.merge_nodes(
            input_nodes, output_nodes
        )
        logger.debug(
            'merged input nodes: %s', input_nodes
        )
        logger.debug(
            'merged output nodes: %s', output_nodes
        )
        (
            self.input_nodes, self.output_nodes
        ) = self.process_nodes(input_nodes, output_nodes)
        logger.debug('input nodes: %s', self.input_nodes)
        logger.debug('output nodes: %s', self.output_nodes)
        self.initialize_nodes_relationship()

    def create_model(self, reset=False):
        self.model_builder = self.get_model_builder()
        self.model_path = self.get_file(
            '%s.%s' % (self.builder.name, self.model_builder.name)
        )
        self.model_params = self.config['model_params']
        self.model = self.model_builder.get_model(
            self, self.model_path, self.model_params,
            input_nodes=self.generate_node_keys_by_nodes(self.input_nodes),
            output_nodes=self.generate_node_keys_by_nodes(self.output_nodes),
            input_nodes_device_type_types=(
                self.generate_device_type_types_by_nodes(
                    self.original_input_nodes
                )
            ),
            output_nodes_device_type_types=(
                self.generate_device_type_types_by_nodes(
                    self.original_output_nodes
                )
            ),
            reset=reset
        )

    def build(self, data=None, force=True):
        logger.debug(
            '%s build model force=%s',
            self, force
        )
        built = self.is_built()
        if force or not built:
            try:
                self.create_nodes(data)
                self.create_model(reset=True)
                self.save_built()
            except Exception as error:
                logger.exception(error)
                raise error
        else:
            logger.debug('%s build is not forced and is already built', self)

    def _get_data_from_timeseries(
            self, session,
            starttime, endtime, nodes
    ):
        time_interval = self.metadata['time_interval']
        device_type_mapping = {}
        device_type_types = {}
        node_keys = []
        for node in nodes:
            node_key = self.get_node_key(node)
            device_type, measurement, device = node_key
            node_keys.append(node_key)
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
            'get data %s from timeseries %s %s: %s',
            node_keys, starttime, endtime, response.columns
        )
        return response

    def _get_data_direct(self, data):
        dataframe = {}
        if isinstance(data, dict):
            for device_type, device_type_data in six.iteritems(data):
                for measurement, measurement_data in six.iteritems(
                    device_type_data
                ):
                    for device, device_data in six.iteritems(measurement_data):
                        key = (measurement, device_type, device)
                        times, values = zip(*device_data.items())
                        dataframe[key] = pd.Series(values, index=times)
            data = pd.DataFrame(dataframe)
        logger.debug(
            'get data directly: %s',
            data.columns
        )
        return data

    def get_data_by_nodes(
        self, nodes, starttime=None, endtime=None, data=None
    ):
        logger.debug('get data nodes: %s', nodes)
        if starttime is not None and endtime is not None:
            with database.influx_session(dataframe=True) as session:
                data = self._get_data_from_timeseries(
                    session,
                    starttime, endtime,
                    nodes
                )
        elif data is not None:
            data = self._get_data_direct(
                data
            )
        if data is not None:
            logger.debug('data columns: %s', data.columns)
            logger.debug('data index: %s', data.index)
        return data

    def get_input_data(
        self, starttime=None, endtime=None, data=None
    ):
        return self.get_data_by_nodes(
            self.unmerged_input_nodes,
            starttime=starttime, endtime=endtime, data=data
        )

    def get_output_data(
        self, starttime=None, endtime=None, data=None
    ):
        return self.get_data_by_nodes(
            self.unmerged_output_nodes,
            starttime=starttime, endtime=endtime, data=data
        )

    def get_data(
        self, starttime=None, endtime=None, data=None
    ):
        data = data or {}
        input_data = self.get_input_data(
            starttime=starttime, endtime=endtime,
            data=data.get('input_data')
        )
        output_data = self.get_output_data(
            starttime=starttime, endtime=endtime,
            data=data.get('output_data')
        )
        return input_data, output_data

    def is_built(self):
        return self.built

    def is_trained(self):
        return self.trained

    def clear_built(self):
        node_path = self.get_file(self.config['nodes'])
        if os.path.exists(node_path):
            os.remove(node_path)
        self.built = False

    def set_built(self):
        self.built = True

    def clear_trained(self):
        if self.model_path and os.path.exists(self.model_path):
            shutil.rmtree(self.model_path)
        self.trained = False

    def set_trained(self):
        self.trained = True

    def unique_nodes(self, nodes):
        new_nodes = []
        node_keys = set()
        for node in nodes:
            node_key = self.get_node_key(node)
            if node_key not in node_keys:
                node_keys.add(node_key)
                new_nodes.append(node)
        return new_nodes

    def process_input_nodes(self, input_nodes):
        return self.unique_nodes(input_nodes)

    def process_output_nodes(self, output_nodes):
        return self.unique_nodes(output_nodes)

    def process_nodes(self, input_nodes, output_nodes):
        return (
            self.process_input_nodes(input_nodes),
            self.process_output_nodes(output_nodes)
        )

    def merge_input_nodes(self, input_nodes):
        return self.unique_nodes(input_nodes)

    def merge_output_nodes(self, output_nodes):
        return self.unique_nodes(output_nodes)

    def merge_nodes(self, input_nodes, output_nodes):
        return (
            self.merge_input_nodes(input_nodes),
            self.merge_output_nodes(output_nodes)
        )

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

    def normalize_input_data(self, input_data):
        if input_data is not None:
            logger.debug('normalize input data %s', input_data.columns)
            input_data = self.normalize_data_by_nodes(
                input_data, self.input_nodes
            )
        return input_data

    def normalize_output_data(self, output_data):
        if output_data is not None:
            logger.debug('normalize output data %s', output_data.columns)
            output_data = self.normalize_data_by_nodes(
                output_data, self.output_nodes
            )
        return output_data

    def normalize_data(self, input_data, output_data):
        logger.debug('normalize data')
        input_data = self.normalize_input_data(
            input_data
        )
        output_data = self.normalize_output_data(
            output_data
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

    def denormalize_data(self, output_data):
        if output_data is not None:
            logger.debug('denormalize_data %s', output_data.columns)
            output_data = self.denormalize_data_by_nodes(
                output_data, self.output_nodes
            )
        return output_data

    def recover_data(self, output_data):
        logger.debug('recover data')
        output_data = self.denormalize_data(
            output_data
        )
        output_data = self.detransform_data(
            output_data
        )
        output_data = self.clean_output_data(output_data)
        return output_data

    def generate_device_type_mapping_by_nodes(self, nodes):
        device_type_mapping = {}
        for node in nodes:
            device_type = node['device_type']
            measurement = node['measurement']
            device = node['device']
            measurement_mapping = device_type_mapping.setdefault(
                device_type, {}
            )
            devices = measurement_mapping.setdefault(
                measurement, [])
            devices.append(device)
        return device_type_mapping

    def generate_device_type_types_by_nodes(self, nodes):
        device_type_types = {}
        for node in nodes:
            device_type = node['device_type']
            measurement = node['measurement']
            measurement_type = node['type']
            measurement_types = device_type_types.setdefault(
                device_type, {}
            )
            measurement_types[measurement] = measurement_type
        return device_type_types

    def generate_original_nodes_by_nodes(self, nodes):
        new_nodes = []
        for node in nodes:
            if 'original_node' in node:
                node = node['original_node']
            new_nodes.append(node)
        return self.unique_nodes(new_nodes)

    def generate_original_output_nodes(self):
        return self.generate_original_nodes_by_nodes(self.output_nodes)

    def generate_original_input_nodes(self):
        return self.generate_original_nodes_by_nodes(self.input_nodes)

    def generate_original_nodes(self):
        return (
            self.generate_original_input_nodes(),
            self.generate_original_output_nodes()
        )

    def generate_unmerged_nodes_by_nodes(self, nodes):
        new_nodes = []
        for node in nodes:
            if 'sub_nodes' in node:
                new_nodes.extend(node['sub_nodes'])
            else:
                new_nodes.append(node)
        return self.unique_nodes(new_nodes)

    def generate_unmerged_input_nodes(self):
        return self.generate_unmerged_nodes_by_nodes(
            self.original_input_nodes
        )

    def generate_unmerged_output_nodes(self):
        return self.generate_unmerged_nodes_by_nodes(
            self.original_output_nodes
        )

    def generate_unmerged_nodes(self):
        return (
            self.generate_unmerged_input_nodes(),
            self.generate_unmerged_output_nodes()
        )

    def generate_node_keys_by_nodes(self, nodes):
        return [self.get_node_key(node) for node in nodes]

    def generate_node_key_mapping_by_nodes(self, nodes):
        return {
            self.get_node_key(node): node for node in nodes
        }

    def recover_prediction_data(self, transformed_data):
        return self.recover_data(transformed_data)

    def recover_expectation_data(self, output_data):
        if output_data is not None:
            node_keys = self.generate_node_keys_by_nodes(
                self.original_output_nodes
            )
            output_data = output_data[node_keys]
        return output_data

    def recover_statistics(self, statistics):
        recoved_statistics = {}
        node_key_mapping = self.generate_node_key_mapping_by_nodes(
            self.output_nodes
        )
        if statistics:
            for key, item in six.iteritems(statistics):
                node = node_key_mapping[key]
                if 'original_node' in node:
                    node = node['original_node']
                key = self.get_node_key(node)
                recoved_statistics[key] = item
        return recoved_statistics

    def recover_test_result(
        self, result, output_data,
        generate_predictions=True, generate_expectations=True
    ):
        if generate_predictions:
            result['predictions'] = self.recover_prediction_data(
                result.get('predictions')
            )
        if generate_expectations:
            result['expectations'] = self.recover_expectation_data(
                output_data
            )
        result['statistics'] = self.recover_statistics(
            result.get('statistics')
        )
        result['device_type_mapping'] = (
            self.generate_device_type_mapping_by_nodes(
                self.original_output_nodes
            )
        )
        result['device_type_types'] = (
            self.generate_device_type_types_by_nodes(
                self.original_output_nodes
            )
        )
        result['model_type'] = self.builder.name
        result['model'] = self.model_builder.name
        return result

    def recover_apply_result(self, result):
        return self.recover_prediction_data(
            result
        )

    def clean_input_data(self, input_data):
        if input_data is not None:
            input_data = input_data.dropna()
        return input_data

    def clean_output_data(self, output_data):
        if output_data is not None:
            output_data = output_data.dropna()
        return output_data

    def clean_data(self, input_data, output_data):
        logger.debug('clean data')
        if input_data is not None and output_data is not None:
            total = pd.concat(
                [input_data, output_data], axis=1,
                keys=['input', 'output']
            )
            total = total.dropna()
            input_data = total['input']
            output_data = total['output']
        else:
            input_data = self.clean_input_data(input_data)
            output_data = self.clean_output_data(output_data)
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
        node_data = None
        node_key = self.get_node_key(node)
        if node_key not in data and 'sub_nodes' in node:
            sub_node_dataframe = {}
            sub_node_keys = []
            for sub_node in node['sub_nodes']:
                sub_node_key = self.get_node_key(sub_node)
                sub_node_keys.append(sub_node_key)
                sub_node_dataframe[sub_node_key] = data[sub_node_key]
            logger.debug('merge %s to %s', sub_node_keys, node_key)
            if sub_node_dataframe:
                node_data = self.get_sub_nodes_aggregator(
                    node.get('sub_nodes_aggregator', None)
                )(pd.DataFrame(
                    sub_node_dataframe
                ))
        else:
            node_data = data[node_key]
        if node_data is not None:
            merged_data[node_key] = node_data

    def merge_input_data(self, input_data):
        if input_data is not None:
            logger.debug('merge input data: %s', input_data.columns)
            input_data = self.merge_data_by_nodes(
                input_data, self.original_input_nodes
            )
            logger.debug('merged input data: %s', input_data.columns)
        return input_data

    def merge_output_data(self, output_data):
        if output_data is not None:
            logger.debug('merge output data: %s', output_data.columns)
            output_data = self.merge_data_by_nodes(
                output_data, self.original_output_nodes
            )
            logger.debug('merged output data: %s', output_data.columns)
        return output_data

    def merge_data(self, input_data, output_data):
        logger.debug('merge data')
        input_data = self.merge_input_data(
            input_data
        )
        output_data = self.merge_output_data(
            output_data
        )
        return input_data, output_data

    def filter_input_data(self, input_data):
        if input_data is not None:
            logger.debug('filter input data: %s', input_data.columns)
            input_data = self.filter_data_by_nodes(
                input_data, self.unmerged_input_nodes
            )
            logger.debug('filtered input data: %s', input_data.columns)
        return input_data

    def filter_data_by_nodes(self, data, nodes):
        node_keys = self.generate_node_keys_by_nodes(nodes)
        return data[node_keys]

    def filter_output_data(self, output_data):
        if output_data is not None:
            logger.debug('filter output data: %s', output_data.columns)
            output_data = self.filter_data_by_nodes(
                output_data, self.unmerged_output_nodes
            )
            logger.debug('filtered output data: %s', output_data.columns)
        return output_data

    def filter_data(self, input_data, output_data):
        logger.debug('filter data')
        input_data = self.filter_input_data(
            input_data
        )
        output_data = self.filter_output_data(
            output_data
        )
        return input_data, output_data

    def transform_data_by_node(self, data, node, transformed_data={}):
        node_key = self.get_node_key(node)
        node_data = None
        if node_key not in data and 'original_node' in node:
            original_node = node['original_node']
            original_node_key = self.get_node_key(original_node)
            logger.debug(
                'transform %s to %s',
                original_node_key, node_key
            )
            orginal_data = data[original_node_key]
            node_data = self.get_node_transformer(
                node.get('transformer', None)
            )(orginal_data)
        else:
            logger.debug('copy %s to transformed data', node_key)
            node_data = data[node_key]
        transformed_data[node_key] = node_data

    def transform_data_by_nodes(self, data, nodes):
        transformed_data = {}
        for node in nodes:
            self.transform_data_by_node(data, node, transformed_data)
        return pd.DataFrame(transformed_data)

    def transform_input_data(self, input_data):
        if input_data is not None:
            logger.debug('transform input data: %s', input_data.columns)
            input_data = self.transform_data_by_nodes(
                input_data, self.input_nodes
            )
            logger.debug('transformed input data: %s', input_data.columns)
        return input_data

    def transform_output_data(self, output_data):
        if output_data is not None:
            logger.debug('transform output data: %s', output_data.columns)
            output_data = self.transform_data_by_nodes(
                output_data, self.output_nodes
            )
            logger.debug('transformed output data: %s', output_data.columns)
        return output_data

    def transform_data(self, input_data, output_data):
        logger.debug('transform data')
        input_data = self.transform_input_data(
            input_data
        )
        output_data = self.transform_output_data(
            output_data
        )
        return input_data, output_data

    def detransform_data_by_node(
        self, data, node, detransformed_data={}
    ):
        node_key = self.get_node_key(node)
        node_data = data[node_key]
        if 'original_node' in node:
            original_node = node['original_node']
            original_node_key = self.get_node_key(original_node)
            logger.debug(
                'detransform %s to %s',
                node_key, original_node_key
            )
            node_key = original_node_key
            node_data = self.get_node_detransformer(
                node.get('detransformer', None)
            )(node_data)
        detransformed_data[node_key] = node_data

    def detransform_data_by_nodes(self, data, nodes):
        detransformed_data = {}
        for node in nodes:
            self.detransform_data_by_node(
                data, node, detransformed_data
            )
        return pd.DataFrame(detransformed_data)

    def detransform_data(
        self, output_data
    ):
        if output_data is not None:
            logger.debug(
                'detransform data: %s', output_data.columns
            )
            output_data = self.detransform_data_by_nodes(
                output_data,
                self.output_nodes
            )
            logger.debug('detransformed data: %s', output_data.columns)
        return output_data

    def process_data(self, input_data, output_data):
        logger.debug('process data')
        input_data, output_data = self.transform_data(
            input_data, output_data
        )
        input_data, output_data = self.normalize_data(
            input_data, output_data
        )
        input_data, output_data = self.clean_data(
            input_data, output_data
        )
        return input_data, output_data

    def train(
        self, starttime=None, endtime=None, data=None,
        force=True, filter_data=True, merge_data=True, process_data=True,
        generate_predictions=True, generate_expectations=True
    ):
        logger.debug('%s train model force=%s', self, force)
        self.load_built()
        if force or not self.is_trained():
            try:
                input_data, output_data = self.get_data(
                    starttime=starttime, endtime=endtime, data=data
                )
                if filter_data:
                    input_data, output_data = self.filter_data(
                        input_data, output_data
                    )
                if merge_data:
                    input_data, output_data = self.merge_data(
                        input_data, output_data
                    )
                if process_data:
                    (
                        processed_input_data, processed_output_data
                    ) = self.process_data(
                        input_data, output_data
                    )
                else:
                    (
                        processed_input_data, processed_output_data
                    ) = (
                        input_data, output_data
                    )
                result = self.model.train(
                    processed_input_data, processed_output_data,
                    generate_predictions=generate_predictions,
                    generate_expectations=generate_expectations
                )
                self.save_trained()
                result = self.recover_test_result(
                    result, output_data,
                    generate_predictions=generate_predictions,
                    generate_expectations=generate_expectations
                )
                return result
            except Exception as error:
                logger.exception(error)
                raise error
        else:
            logger.debug(
                '%s train model is not forced and is already trained', self
            )

    def test(
        self, starttime=None, endtime=None, data=None,
        filter_data=True, merge_data=True, process_data=True,
        generate_predictions=True, generate_expectations=True
    ):
        logger.debug('%s test model', self)
        self.load_built()
        self.load_trained()
        try:
            input_data, output_data = self.get_data(
                starttime=starttime, endtime=endtime, data=data
            )
            if filter_data:
                input_data, output_data = self.filter_data(
                    input_data, output_data
                )
            if merge_data:
                input_data, output_data = self.merge_data(
                    input_data, output_data
                )
            if process_data:
                (
                    processed_input_data, processed_output_data
                ) = self.process_data(
                    input_data, output_data
                )
            else:
                (
                    processed_input_data, processed_output_data
                ) = (
                    input_data, output_data
                )
            result = self.model.test(
                processed_input_data, processed_output_data,
                generate_predictions=generate_predictions,
                generate_expectations=generate_expectations
            )
            result = self.recover_test_result(
                result, output_data,
                generate_predictions=generate_predictions,
                generate_expectations=generate_expectations
            )
            return result
        except Exception as error:
            logger.exception(error)
            raise error

    def apply(
        self, starttime=None, endtime=None, data=None,
        filter_data=True, merge_data=True, process_data=True
    ):
        logger.debug('%s apply model', self)
        self.laod_built()
        self.load_trained()
        try:
            input_data, _ = self.get_data(
                starttime=starttime, endtime=endtime, data=data
            )
            if filter_data:
                input_data, _ = self.filter_data(
                    input_data, None
                )
            if merge_data:
                input_data, _ = self.merge_data(
                    input_data, None
                )
            if process_data:
                (
                    processed_input_data, _
                ) = self.process_data(
                    input_data, None
                )
            else:
                processed_input_data = input_data
            result = self.model.apply(
                processed_input_data
            )
            result = self.recover_apply_result(result)
            return result
        except Exception as error:
            logger.exception(error)
            raise error

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
