import abc
import logging
import numpy as np
import os
import os.path
import pandas as pd
import shutil
import six
import tensorflow as tf


logger = logging.getLogger(__name__)


class BaseModel(object):
    def __init__(
        self, model_type, model_path, input_nodes, output_nodes
    ):
        self.model_type = model_type
        self.model_path = model_path
        self.input_nodes = input_nodes
        self.output_nodes = output_nodes
        self.features = [
            tf.contrib.layers.real_valued_column(
                'inputs', dimension=len(self.input_nodes)
            )
        ]
        logger.debug('features: %s', self.features)
        self.estimators = self.create_estimators()

    def get_test_result_mse(self, prediction, output):
        logger.debug('prediction: %s', prediction)
        logger.debug('ouput: %s', output)
        return np.mean(np.square(prediction - output))

    def get_test_result_rsquare(self, prediction, output):
        output_mean = np.mean(output)
        ss_tot = np.sum(np.square(output - output_mean))
        ss_reg = np.sum(np.square(prediction - output))
        if ss_tot < 0.01:
            return 0
        return 1 - ss_reg / ss_tot

    def test_data(
        self, input_data, output_data
    ):
        x = self.get_inputs(input_data)
        predictions = {}
        expectations = {}
        statistics = {}
        for column, estimator in six.iteritems(self.get_estimators()):
            prediction = np.array(list(estimator.predict(x=x)))
            expected = self.get_output(output_data, column)
            predictions[column] = prediction
            expectations[column] = expected
            statistics[column] = {
                'MSE': self.get_test_result_mse(
                    prediction, expected
                ),
                'rsquare': self.get_test_result_rsquare(
                    prediction, expected
                )
            }
        return {
            'predictions': pd.DataFrame(predictions),
            'expectations': pd.DataFrame(expectations),
            'statistics': statistics
        }

    def create_estimator(self, model_path):
        return None

    def create_estimators(self):
        estimators = {}
        for node in self.output_nodes:
            path = os.path.join(self.model_path, '.'.join(node))
            shutil.rmtree(path)
            estimators[node] = self.create_estimator(path)
        return estimators

    def get_estimator(self, node):
        return self.estimators[node]

    def get_estimators(self):
        return self.estimators

    def get_outputs(self, output_data):
        return {
            'outputs': output_data[self.output_nodes].values
        }

    def get_output(self, output_data, column):
        return output_data[column].values

    def get_inputs(self, input_data):
        return {
            'inputs': input_data[self.input_nodes].values
        }

    def get_input(self, input_data, column):
        return input_data[column].value

    def train(
        self, input_data, output_data
    ):
        x = self.get_inputs(input_data)
        for column, estimator in six.iteritems(self.get_estimators()):
            y = self.get_output(output_data, column)
            input_fn = tf.contrib.learn.io.numpy_input_fn(
                x,
                y,
                batch_size=100,
                num_epochs=1000
            )
            estimator.fit(input_fn=input_fn, steps=1000)
        return self.test_data(
            input_data, output_data
        )

    def test(self, input_data, output_data):
        return self.test_data(
            input_data, output_data
        )

    def apply(self, input_data, output_data):
        pass

    def get_estimator_variables(self, estimator):
        estimator_variables = {}
        for variable_name in estimator.get_variable_names():
            variable = estimator.get_variable_value(variable_name)
            logger.debug('variable %s value %r', variable_name, variable)
            estimator_variables[variable_name] = variable.tolist()
        return estimator_variables

    def save(self):
        estimators_variables = {}
        for column, estimator in six.iteritems(self.get_estimators()):
            column_name = '.'.join(column)
            estimators_variables[column_name] = self.get_estimator_variables(
                estimator
            )
        return estimators_variables

    def load(self):
        self.estimators = self.create_estimators()

    def __str__(self):
        return '%s[model_type=%s]' % (
            self.__class__.__name__, self.model_type
        )


@six.add_metaclass(abc.ABCMeta)
class BaseModelBuilder(object):
    def create_model(
        self, model_type, model_path, input_nodes, output_nodes
    ):
        return BaseModel(
            model_type, model_path, input_nodes, output_nodes
        )

    def get_model(
        self, model_type, model_path, input_nodes, output_nodes
    ):
        return self.create_model(
            model_type, model_path, input_nodes, output_nodes
        )

    def __str__(self):
        return '%s' % self.__class__.__name__
