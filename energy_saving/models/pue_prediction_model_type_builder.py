import logging
import pandas
import six

from energy_saving.models import base_model_type_builder


logger = logging.getLogger(__name__)


class PUEPredictionModelType(
    base_model_type_builder.BaseModelType
):
    def process_output_nodes(self, output_nodes):
        reduced_nodes = []
        node_map = set()
        for output_node in output_nodes:
            device_type = output_node['device_type']
            measurement = output_node['measurement']
            if (device_type, measurement) not in node_map:
                node_map.add((device_type, measurement))
                output_node['device'] = 'total'
                reduced_nodes.append(output_node)
        return reduced_nodes

    def process_output_data(self, output_data):
        columns = list(output_data.columns)
        column_groups = {}
        for column in columns:
            device_type, measurement, device = column
            column_group = column_groups.setdefault(
                (device_type, measurement, 'total'), []
            )
            column_group.append(output_data[column])
        dataframe = {}
        for key, value in six.iteritems(column_groups):
            dataframe[key] = sum(value)
        return pandas.DataFrame(dataframe)


class PUEPredictionModelTypeBuilder(
    base_model_type_builder.BaseModelTypeBuilder
):
    def create_model_type(self, datacenter):
        return PUEPredictionModelType(datacenter, self)
