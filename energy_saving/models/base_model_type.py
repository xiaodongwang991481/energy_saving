from abc import ABC
from abc import abstractmethod


class BaseModelType(ABC):
    def build(datacenter):
        pass

    def train(datacenter):
        pass

    def test(datacenter):
        pass

    def apply(datacenter):
        pass

    @abstractmethod
    def get_data(datacenter, metadata):
        pass

    @abstractmethod
    def get_metadatadata(datacenter):
        pass
