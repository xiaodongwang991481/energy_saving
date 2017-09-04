import logging

from energy_saving.models import base_model_type_builder
from energy_saving.models import model_type_builder_manager


logger = logging.getLogger(__name__)
manager = model_type_builder_manager.manager


class ControllerAttrOptimazationModelType(
    base_model_type_builder.BaseModelType
):
    def __init__(self, datacenter, builder):
        super(ControllerAttrOptimazationModelType, self).__init__(
            datacenter, builder
        )
        self.pue_prediction_builder = (
            manager.get_model_type_builder('pue_prediction')
        )
        self.sensor_attributes_prediction_builder = (
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

    def is_trained(self):
        return (
            self.is_built() and
            self.pue_prediction.is_trained() and
            self.sensor_attributes_predition.is_trained()
        )

    def save_trained(self):
        pass

    def merge_test_result(self, pue_result, sensor_attributes_result):
        result = {}
        result['statistics'] = {}
        result['statistics'].update(pue_result.get('statistics') or {})
        result['statistics'].update(
            sensor_attributes_result.get('statistics') or {}
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
        result['model'] = None
        return result

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
                        input_data, output_data
                    ) = self.process_data(
                        input_data, output_data
                    )
                pue_result = self.pue_prediction.train(
                    data={
                        'input_data': input_data,
                        'output_data': output_data
                    }, force=force,
                    filter_data=False, merge_data=False, process_data=False,
                    generate_predictions=False, generate_expectations=False
                )
                sensor_attributes_result = (
                    self.sensor_attributes_predition.train(
                        data={
                            'input_data': input_data,
                            'output_data': output_data
                        }, force=force,
                        filter_data=False, merge_data=False,
                        process_data=False,
                        generate_predictions=False,
                        generate_expectations=False
                    )
                )
                self.save_trained()
                result = self.merge_test_result(
                    pue_result, sensor_attributes_result
                )
                return result
            except Exception as error:
                logger.exception(error)
                raise error
        else:
            logger.debug(
                '%s train model is not forced and is already trained', self
            )


class ControllerAttrOptimazationModelTypeBuilder(
    base_model_type_builder.BaseModelTypeBuilder
):
    def create_model_type(self, datacenter):
        return ControllerAttrOptimazationModelType(datacenter, self)
