import logging
import math

from energy_saving.models import base_model_type_builder


logger = logging.getLogger(__name__)


class PUEPredictionModelType(
    base_model_type_builder.BaseModelType
):
    def merge_output_nodes(self, output_nodes):
        device_unit = None
        device_typename = None
        device_mean = 0
        device_deviation = 0
        sub_nodes = []
        for output_node in output_nodes:
            device_type = output_node['device_type']
            measurement = output_node['measurement']
            if device_type != 'controller_power_supply_attribute':
                continue
            if measurement != 'power':
                continue
            device_unit = output_node['unit']
            device_typename = output_node['type']
            device_mean += output_node['mean']
            device_deviation += output_node['deviation'] ** 2
            sub_nodes.append(output_node)
        return [{
            'device_type': device_type,
            'measurement': measurement,
            'device': 'total',
            'unit': device_unit,
            'type': device_typename,
            'mean': device_mean,
            'deviation': math.sqrt(device_deviation),
            'sub_nodes': sub_nodes,
            'sub_node_aggregator': 'sum'
        }]

    def process_output_nodes(self, output_nodes):
        processed_output_nodes = []
        for output_node in output_nodes:
            processed_output_nodes.append({
                'device_type': output_node['device_type'],
                'measurement': output_node['measurement'],
                'device': 'shifted_%s' % output_node['device'],
                'unit': output_node['unit'],
                'type': output_node['type'],
                'mean': output_node['mean'],
                'deviation': output_node['deviation'],
                'transformer': 'shift',
                'detransformer': 'unshift',
                'original_node': output_node
            })
        return processed_output_nodes


class PUEPredictionModelTypeBuilder(
    base_model_type_builder.BaseModelTypeBuilder
):
    def create_model_type(self, datacenter):
        return PUEPredictionModelType(datacenter, self)
