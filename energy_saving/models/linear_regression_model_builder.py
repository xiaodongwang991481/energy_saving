import logging
import tensorflow as tf

from energy_saving.models import base_model_builder


logger = logging.getLogger(__name__)


class LinearRegression(
    base_model_builder.BaseModel
):
    def create_variables(self):
        self.features = [
            tf.contrib.layers.real_valued_column(
                'inputs', dimension=len(self.input_nodes)
            )
        ]
        logger.debug('features: %s', self.features)

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
        self, model_type, model_path, model_params,
        input_nodes, output_nodes,
        input_nodes_device_type_types, output_nodes_device_type_types,
        reset=False
    ):
        return LinearRegression(
            self, model_type, model_path, model_params,
            input_nodes=input_nodes, output_nodes=output_nodes,
            input_nodes_device_type_types=input_nodes_device_type_types,
            output_nodes_device_type_types=output_nodes_device_type_types,
            reset=reset
        )
