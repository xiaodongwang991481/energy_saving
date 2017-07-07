import logging
import stevedore


class ModelTypeManager(stevedore.extension.ExtensionManager):

    def __init__(self):
        self.model_types = {}
        super(ModelTypeManager, self).__init__(
            'energy_saving.model_type',
            invoke_on_load=True,
        )
        self._register_model_types()

    def _register_model_types(self):
        for ext in self:
            logging.debug('register model type %s', ext.name)
            self.model_types[ext.name] = ext

    def get_model_type(self, name):
        logging.debug(
            'get model type %s from model types %s', name, self.model_types
        )
        if name in self.model_types:
            return self.model_types[name].obj
        return self.model_types['default'].obj
