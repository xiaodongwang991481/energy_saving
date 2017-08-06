import abc
import logging
import six


logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class BaseModel(object):
    def build(self, input_nodes, output_nodes):
        pass

    def train(self, input_data, output_data):
        pass

    def test(self, input_data, output_data):
        pass

    def apply(self, input_data, output_data):
        pass

    def load(self):
        pass

    def save(self):
        pass
