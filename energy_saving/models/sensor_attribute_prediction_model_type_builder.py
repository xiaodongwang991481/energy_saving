import logging

from energy_saving.models import base_model_type_builder


logger = logging.getLogger(__name__)


class SensorAttrPredictionModelType(
    base_model_type_builder.BaseModelType
):
    def process_output_nodes(self, output_nodes):
        processed_output_nodes = []
        for output_node in output_nodes:
            device_type = output_node['device_type']
            measurement = output_node['measurement']
            if device_type == 'sensor_attribute':
                output_node = {
                    'device_type': device_type,
                    'measurement': measurement,
                    'device': 'shifted_%s' % output_node['device'],
                    'unit': output_node['unit'],
                    'type': output_node['type'],
                    'mean': output_node['mean'],
                    'deviation': output_node['deviation'],
                    'transformer': 'shift',
                    'detransformer': 'unshift',
                    'original_node': output_node
                }
            processed_output_nodes.append(output_node)
        return processed_output_nodes


class SensorAttrPredictionModelTypeBuilder(
    base_model_type_builder.BaseModelTypeBuilder
):
    def create_model_type(self, datacenter):
        return SensorAttrPredictionModelType(datacenter, self)
