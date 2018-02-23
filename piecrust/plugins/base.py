import os.path
import sys
import logging
import importlib


logger = logging.getLogger(__name__)


class PieCrustPlugin(object):
    def getFormatters(self):
        return []

    def getTemplateEngines(self):
        return []

    def getTemplateEngineExtensions(self, engine_name):
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

    def getPipelines(self):
        return []

    def getPublishers(self):
        return []

    def getTaskRunners(self):
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
            'getFormatters',
            initialize=True, register_timer=True,
            order_key=lambda f: f.priority)

    def getTemplateEngines(self):
        return self._getPluginComponents(
            'getTemplateEngines',
            initialize=True, register_timer=True,
            register_timer_suffixes=['_segment', '_layout'])

    def getTemplateEngineExtensions(self, engine_name):
        return self._getPluginComponents('getTemplateEngineExtensions',
                                         engine_name)

    def getDataProviders(self):
        return self._getPluginComponents('getDataProviders')

    def getProcessors(self):
        return self._getPluginComponents(
            'getProcessors',
            initialize=True, register_timer=True,
            order_key=lambda p: p.priority)

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

    def getPipelines(self):
        return self._getPluginComponents('getPipelines')

    def getPublishers(self):
        return self._getPluginComponents('getPublishers')

    def getTaskRunners(self):
        return self._getPluginComponents('getTaskRunners')

    def _ensureLoaded(self):
        if self._plugins is not None:
            return

        from piecrust.plugins.builtin import BuiltInPlugin
        self._plugins = [BuiltInPlugin()]

        to_install = self.app.config.get('site/plugins')
        if to_install:
            for name in to_install:
                plugin = self._loadPlugin(name)
                if plugin is not None:
                    self._plugins.append(plugin)

        for plugin in self._plugins:
            plugin.initialize(self.app)

    def _loadPlugin(self, plugin_name):
        mod_name = 'piecrust_%s' % plugin_name
        try:
            # Import from the current environment.
            mod = importlib.import_module(mod_name)
        except ImportError as ex:
            mod = None

        if mod is None:
            # Import as a loose Python file from the plugins dir.
            for plugins_dir in self.app.plugins_dirs:
                pfile = os.path.join(plugins_dir, plugin_name + '.py')
                if os.path.isfile(pfile):
                    if sys.version_info[1] >= 5:
                        # Python 3.5+
                        from importlib.util import (spec_from_file_location,
                                                    module_from_spec)
                        spec = spec_from_file_location(plugin_name, pfile)
                        mod = module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        sys.modules[mod_name] = mod
                    else:
                        # Python 3.4, 3.3.
                        from importlib.machinery import SourceFileLoader
                        mod = SourceFileLoader(
                            plugin_name, pfile).load_module()
                        sys.modules[mod_name] = mod

        if mod is None:
            logger.error("Failed to load plugin '%s'." % plugin_name)
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

        return plugin

    def _getPluginComponents(self, name, *args,
                             initialize=False,
                             register_timer=False,
                             register_timer_suffixes=None,
                             order_key=None):
        if name in self._componentCache:
            return self._componentCache[name]

        all_components = []
        for plugin in self.plugins:
            plugin_components = getattr(plugin, name)(*args)
            # Make sure it's a list in case it was an iterator.
            plugin_components = list(plugin_components)
            all_components += plugin_components

            if initialize:
                for comp in plugin_components:
                    comp.initialize(self.app)

            if register_timer:
                for comp in plugin_components:
                    if not register_timer_suffixes:
                        self.app.env.stats.registerTimer(
                            comp.__class__.__name__)
                    else:
                        for s in register_timer_suffixes:
                            self.app.env.stats.registerTimer(
                                comp.__class__.__name__ + s)

        if order_key is not None:
            all_components.sort(key=order_key)

        self._componentCache[name] = all_components
        return all_components

