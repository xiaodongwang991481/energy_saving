import logging
import stevedore


logger = logging.getLogger(__name__)


class ModelNotFoundException(Exception):
    pass


class ModelManager(stevedore.extension.ExtensionManager):

    def __init__(self):
        self.models = {}
        super(ModelManager, self).__init__(
            'energy_saving.models',
            invoke_on_load=True
        )
        self._register_models()

    def _register_models(self):
        for ext in self:
            logging.debug('register model %s', ext.name)
            self.models[ext.name] = ext

    def get_model(self, name):
        logging.debug(
            'get model %s '
            'from models %s',
            name, self.models
        )
        if name in self.models:
            return self.models[name].obj
        raise ModelNotFoundException(
            'model %s does not found' % name
        )
