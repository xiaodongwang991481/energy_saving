import logging
import stevedore


logger = logging.getLogger(__name__)


class ModelTypeBuilderNotFoundException(Exception):
    pass


class ModelTypeBuilderManager(stevedore.extension.ExtensionManager):

    def __init__(self):
        self.model_type_builders = {}
        super(ModelTypeBuilderManager, self).__init__(
            'energy_saving.model_type_builders',
            invoke_on_load=False
        )
        logger.info('model type builders: %s', self)
        self._register_model_type_builders()

    def _register_model_type_builders(self):
        for ext in self:
            logger.debug('register model type builder %s', ext.name)
            self.model_type_builders[ext.name] = ext
            ext.obj = ext.plugin(ext.name)

    def get_model_type_builder(self, name):
        logger.debug(
            'get model type builder %s '
            'from model type builders %s',
            name, self.model_type_builders
        )
        if name in self.model_type_builders:
            plugin_obj = self.model_type_builders[name].obj
            logger.debug(
                'get model type builder %s plugin: %s',
                name, plugin_obj
            )
            return plugin_obj
        raise ModelTypeBuilderNotFoundException(
            'model type builder %s does not found' % name
        )
