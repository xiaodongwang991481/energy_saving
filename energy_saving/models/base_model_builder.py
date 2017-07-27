import abc
import logging
import six


logger = logging.getLogger(__name__)


class BaseModel(object):
    def __init__(self, model_type):
        self.model_type = model_type

    def build(self):
        logger.debug(
            '%s build model', self
        )

    def train(self, input_data, output_data):
        logger.debug(
            '%s train mode; with input data %s output data %s',
            self, input_data, output_data
        )

    def test(self, input_data, output_data):
        pass

    def apply(self, input_data, output_data):
        pass

    def save(self):
        pass

    def load(self):
        pass

    def __str__(self):
        return '%s[model_type=%s]' % (
            self.__class__.__name__, self.model_type
        )


@six.add_metaclass(abc.ABCMeta)
class BaseModelBuilder(object):
    def create_model(self, model_type):
        return BaseModel(model_type)

    def get_model(self, model_type):
        return self.create_model(model_type)

    def __str__(self):
        return '%s' % self.__class__.__name__
