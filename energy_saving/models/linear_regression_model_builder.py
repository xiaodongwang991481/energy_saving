import logging

from energy_saving.models import base_model_builder


logger = logging.getLogger(__name__)


class LinearRegression(
    base_model_builder.BaseModel
):
    pass


class LinearRegressionBuilder(
    base_model_builder.BaseModelBuilder
):
    def create_model(self, model_type):
        return LinearRegression(model_type)
