from abc import ABC
from abc import abstractmethod


class BaseModelType(ABC):
    def build(self, datacenter):
        metadata = self.get_meatadata(datacenter)
        return metadata

    def train(self, datacenter):
        metadata = self.get_meatadata(datacenter)
        data = self.get_data(datacenter, metadata)
        return data

    def test(self, datacenter):
        pass

    def apply(self, datacenter):
        pass

    @abstractmethod
    def get_data(self, datacenter, metadata):
        pass

    @abstractmethod
    def get_metadatadata(self, datacenter):
        pass
