import logging
import math
import pandas as pd

from energy_saving.models import base_model_type_builder


logger = logging.getLogger(__name__)


class PUEPredictionModelType(
    base_model_type_builder.BaseModelType
):
    def process_nodes(self, input_nodes, output_nodes):
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
        output_node = {
            'device_type': 'controller_power_supply_attribute',
            'measurement': 'power',
            'device': 'total',
            'unit': device_unit,
            'type': device_typename,
            'mean': device_mean,
            'deviation': math.sqrt(device_deviation),
            'sub_nodes': sub_nodes
        }
        return input_nodes, [output_node]

    def merge_data(self, input_data, output_data):
        if output_data is not None:
            merged_data = {}
            for node in self.output_nodes:
                node_key = self.get_node_key(node)
                node_data = pd.DataFrame(
                    output_data[(
                        'controller_power_supply_attribute', 'power'
                    )]
                ).sum(axis=1)
                merged_data[node_key] = node_data
            output_data = pd.DataFrame(merged_data)
        return input_data, output_data


class PUEPredictionModelTypeBuilder(
    base_model_type_builder.BaseModelTypeBuilder
):
    def create_model_type(self, datacenter):
        return PUEPredictionModelType(datacenter, self)
