import logging
import numpy as np
import tensorflow as tf
# from tensorflow.contrib.learn.python.learn.estimators.estimator import (
#     SKCompat
# )

from energy_saving.models import base_model_builder


logger = logging.getLogger(__name__)


class RandomForestRegression(
    base_model_builder.BaseModel
):
    def create_variables(self):
        tensor_forest = tf.contrib.tensor_forest.python.tensor_forest
        self.hparams = tensor_forest.ForestHParams(
            num_trees=self.model_params.get('num_trees', 3),
            max_nodes=self.model_params.get('max_nodes', 1000),
            num_classes=1,
            num_features=len(self.input_nodes),
            regression=True, split_after_samples=20
        )
        logger.debug('hparams: %s', self.hparams)

    def create_estimator(self, model_path):
        random_forest = tf.contrib.tensor_forest.client.random_forest
        return random_forest.TensorForestEstimator(
            self.hparams,
            model_dir=model_path
        )

    def get_inputs(self, input_data):
        return {
            'inputs': input_data[self.input_nodes].values.astype(np.float32)
        }

    def get_outputs(self, output_data):
        return {
            'outputs': output_data[self.output_nodes].values.astype(np.float32)
        }

    def get_output(self, output_data, column):
        return output_data[column].values.astype(np.float32)

    def get_input(self, input_data, column):
        return input_data[column].values.astype(np.float32)

    def get_prediction(self, estimator, x):
        prediction = [
            item['scores'] for item in list(estimator.predict(x=x))
        ]
        return np.array(prediction)


class RandomForestRegressionBuilder(
    base_model_builder.BaseModelBuilder
):
    def create_model(
        self, model_type, model_path, model_params,
        input_nodes, output_nodes,
        input_nodes_device_type_types, output_nodes_device_type_types,
        reset=False
    ):
        return RandomForestRegression(
            self, model_type, model_path, model_params,
            input_nodes=input_nodes, output_nodes=output_nodes,
            input_nodes_device_type_types=input_nodes_device_type_types,
            output_nodes_device_type_types=output_nodes_device_type_types,
            reset=reset
        )
