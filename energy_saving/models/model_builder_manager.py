import logging
import stevedore


logger = logging.getLogger(__name__)


class ModelBuilderNotFoundException(Exception):
    pass


class ModelBuilderManager(stevedore.extension.ExtensionManager):

    def __init__(self):
        self.model_builders = {}
        super(ModelBuilderManager, self).__init__(
            'energy_saving.model_builders',
            invoke_on_load=True
        )
        self._register_model_builders()

    def _register_model_builders(self):
        for ext in self:
            logging.debug('register model builder %s', ext.name)
            self.model_builders[ext.name] = ext

    def get_model_builder(self, name):
        logging.debug(
            'get model builder %s '
            'from model builders %s',
            name, self.model_builders
        )
        if name in self.model_builders:
            return self.model_builders[name].obj
        raise ModelBuilderNotFoundException(
            'model builder %s does not found' % name
        )
