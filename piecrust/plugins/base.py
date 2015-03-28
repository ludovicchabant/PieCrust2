import logging
import importlib


logger = logging.getLogger(__name__)


class PieCrustPlugin(object):
    def getFormatters(self):
        return []

    def getTemplateEngines(self):
        return []

    def getDataProviders(self):
        return []

    def getProcessors(self):
        return []

    def getImporters(self):
        return []

    def getCommands(self):
        return []

    def getCommandExtensions(self):
        return []

    def getBakerAssistants(self):
        return []

    def getSources(self):
        return []

    def initialize(self, app):
        pass


class PluginLoader(object):
    def __init__(self, app):
        self.app = app
        self._plugins = None
        self._componentCache = {}

    @property
    def plugins(self):
        self._ensureLoaded()
        return self._plugins

    def getFormatters(self):
        return self._getPluginComponents(
                'getFormatters', True, order_key=lambda f: f.priority)

    def getTemplateEngines(self):
        return self._getPluginComponents('getTemplateEngines', True)

    def getDataProviders(self):
        return self._getPluginComponents('getDataProviders')

    def getProcessors(self):
        return self._getPluginComponents(
                'getProcessors', True, order_key=lambda p: p.priority)

    def getImporters(self):
        return self._getPluginComponents('getImporters')

    def getCommands(self):
        return self._getPluginComponents('getCommands')

    def getCommandExtensions(self):
        return self._getPluginComponents('getCommandExtensions')

    def getBakerAssistants(self):
        return self._getPluginComponents('getBakerAssistants')

    def getSources(self):
        return self._getPluginComponents('getSources')

    def _ensureLoaded(self):
        if self._plugins is not None:
            return

        from piecrust.plugins.builtin import BuiltInPlugin
        self._plugins = [BuiltInPlugin()]

        to_install = self.app.config.get('site/plugins')
        if to_install:
            for p in to_install:
                self._loadPlugin(p)

        for plugin in self._plugins:
            plugin.initialize(self.app)

    def _loadPlugin(self, plugin_name):
        try:
            mod = importlib.import_module('piecrust_' + plugin_name)
        except ImportError as ex:
            logger.error("Failed to load plugin '%s'." % plugin_name)
            logger.error(ex)
            return

        plugin_class = getattr(mod, '__piecrust_plugin__', None)
        if plugin_class is None:
            logger.error("Plugin '%s' doesn't specify any "
                         "`__piecrust_plugin__` class." % plugin_name)
            return

        try:
            plugin = plugin_class()
        except Exception as ex:
            logger.error("Failed to create plugin '%s': %s" %
                         (plugin_name, ex))
            return

        self._plugins.append(plugin)

    def _getPluginComponents(self, name, initialize=False, order_key=None):
        if name in self._componentCache:
            return self._componentCache[name]

        all_components = []
        for plugin in self.plugins:
            plugin_components = getattr(plugin, name)()
            all_components += plugin_components
            if initialize:
                for comp in plugin_components:
                    comp.initialize(self.app)

        if order_key is not None:
            all_components.sort(key=order_key)

        self._componentCache[name] = all_components
        return all_components

