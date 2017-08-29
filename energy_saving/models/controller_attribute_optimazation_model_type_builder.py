import logging

from energy_saving.models import base_model_type_builder
from energy_saving.models import model_type_builder_manager


logger = logging.getLogger(__name__)
manager = model_type_builder_manager.manager


class ControllerAttrOptimazationModelType(
    base_model_type_builder.BaseModelTYpe
):
    def __init__(self, datacenter, builder):
        super(ControllerAttrOptimazationModelType, self).__init__(
            datacenter, builder
        )
        self.pue_prediction_builder = (
            manager.get_model_type_builder('pue_prediction')
        )
        self.sensor_attributes_predition_builder = (
            manager.get_model_type_builder('sensor_attributes_prediction')
        )
        self.pue_prediction = (
            self.pue_prediction_builder.get_model_type(datacenter)
        )
        self.sensor_attributes_predition = (
            self.sensor_attributes_prediction_builder.get_model_type(
                datacenter
            )
        )

    def build(self, data=None, force=True):
        data = data or {}
        pue_prediction_data = data.get('pue_prediction')
        sensor_attributes_prediction = data.get(
            'sensor_attributes_prediction'
        )
        self.pue_prediction.build(data=pue_prediction_data, force=False)
        self.sensor_attributes_predition.build(
            data=sensor_attributes_prediction, force=False
        )
        super(ControllerAttrOptimazationModelType, self).build(
            data, force=force
        )

    def create_model(self, reset=False):
        pass

    def load_model(self):
        pass

    def save_model(self):
        pass

    def is_built(self):
        return (
            self.pue_prediction.is_built() and
            self.sensor_attributes_predition.is_built()
        )

    def is_trained(self):
        return (
            self.pue_prediction.is_trained() and
            self.sensor_attributes_predition.is_trained()
        )

    def create_nodes(self, data=None):
        self.input_nodes = self.unique_nodes(
            self.pue_prediction.input_nodes +
            self.sensor_attributes_predition.input_nodes
        )
        self.output_nodes = self.unique_nodes(
            self.pue_prediction.output_nodes +
            self.sensor_attributes_predition.output_nodes
        )
        self.initialize_nodes_relationship()

    def train(
        self, starttime=None, endtime=None, data=None,
        force=True
    ):
        pass


class ControllerAttrOptimazationModelTypeBuilder(
    base_model_type_builder.BaseModelTypeBuilder
):
    def create_model_type(self, datacenter):
        return ControllerAttrOptimazationModelType(datacenter, self)
