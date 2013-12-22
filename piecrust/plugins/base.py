import os


class PieCrustPlugin(object):
    def getFormatters(self):
        return []

    def getTemplateEngines(self):
        return []

    def getDataProviders(self):
        return []

    def getFileSystems(self):
        return []

    def getProcessors(self):
        return []

    def getImporters(self):
        return []

    def getCommands(self):
        return []

    def getRepositories(self):
        return []

    def getBakerAssistants(self):
        return []

    def initialize(self, app):
        pass


class PluginLoader(object):
    def __init__(self, app):
        self.app = app
        self._plugins = None
        self._pluginsMeta = None
        self._componentCache = {}

    @property
    def plugins(self):
        self._ensureLoaded()
        return self._plugins

    def getFormatters(self):
        return self._getPluginComponents('getFormatters', True,
                order_key=lambda f: f.priority)

    def getTemplateEngines(self):
        return self._getPluginComponents('getTemplateEngines', True)

    def getDataProviders(self):
        return self._getPluginComponents('getDataProviders')

    def getFileSystems(self):
        return self._getPluginComponents('getFileSystems')

    def getProcessors(self):
        return self._getPluginComponents('getProcessors', True,
                order_key=lambda p: p.priority)

    def getImporters(self):
        return self._getPluginComponents('getImporters')

    def getCommands(self):
        return self._getPluginComponents('getCommands')

    def getRepositories(self):
        return self._getPluginComponents('getRepositories', True)

    def getBakerAssistants(self):
        return self._getPluginComponents('getBakerAssistants')

    def _ensureLoaded(self):
        if self._plugins is not None:
            return

        from piecrust.plugins.builtin import BuiltInPlugin
        self._plugins = [BuiltInPlugin()]
        self._pluginsMeta = {self._plugins[0].name: False}

        for d in self.app.plugins_dirs:
            _, dirs, __ = next(os.walk(d))
            for dd in dirs:
                self._loadPlugin(os.path.join(d, dd))

        for plugin in self._plugins:
            plugin.initialize(self.app)

    def _loadPlugin(self, plugin_dir):
        pass

    def _getPluginComponents(self, name, initialize=False, order_cmp=None, order_key=None):
        if name in self._componentCache:
            return self._componentCache[name]

        all_components = []
        for plugin in self.plugins:
            plugin_components = getattr(plugin, name)()
            all_components += plugin_components
            if initialize:
                for comp in plugin_components:
                    comp.initialize(self.app)

        if order_cmp is not None or order_key is not None:
            all_components.sort(cmp=order_cmp, key=order_key)

        self._componentCache[name] = all_components
        return all_components

