import logging
import tensorflow as tf

from energy_saving.models import base_model_builder


logger = logging.getLogger(__name__)


class LinearRegression(
    base_model_builder.BaseModel
):
    def __init__(
        self, model_type, model_path, input_nodes, output_nodes
    ):
        super(LinearRegression, self).__init__(
            model_type, model_path, input_nodes, output_nodes
        )

    def create_estimator(self, model_path):
        return tf.contrib.learn.LinearRegressor(
            feature_columns=self.features,
            model_dir=model_path,
            enable_centered_bias=True
        )


class LinearRegressionBuilder(
    base_model_builder.BaseModelBuilder
):
    def create_model(
        self, model_type, model_path, input_nodes, output_nodes
    ):
        return LinearRegression(
            model_type, model_path, input_nodes, output_nodes
        )
