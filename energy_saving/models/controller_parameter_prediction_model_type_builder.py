from energy_saving.models import base_model_type_builder


class ControllerParamPredictionModelType(
    base_model_type_builder.BaseModelType
):
    pass


class ControllerParamPredictionModelTypeBuilder(
    base_model_type_builder.BaseModelTypeBuilder
):
    def create_model_type(self, datacenter):
        return ControllerParamPredictionModelType(
            datacenter, self
        )
