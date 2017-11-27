import time
import os.path
import logging
import urllib.parse
from werkzeug.utils import cached_property
from piecrust import (
    RESOURCES_DIR,
    CACHE_DIR, TEMPLATES_DIR, ASSETS_DIR,
    THEME_DIR, PLUGINS_DIR,
    CONFIG_PATH, THEME_CONFIG_PATH)
from piecrust.appconfig import PieCrustConfiguration
from piecrust.cache import ExtensibleCache, NullExtensibleCache
from piecrust.configuration import ConfigurationError
from piecrust.environment import StandardEnvironment
from piecrust.page import Page
from piecrust.plugins.base import PluginLoader
from piecrust.routing import Route
from piecrust.sources.base import REALM_THEME
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


class PieCrust(object):
    def __init__(self, root_dir, cache=True, debug=False, theme_site=False,
                 env=None, cache_key=None):
        self.root_dir = root_dir
        self.debug = debug
        self.theme_site = theme_site
        self.plugin_loader = PluginLoader(self)
        self.cache_key = cache_key or 'default'

        if cache:
            self.cache = ExtensibleCache(self.cache_dir)
        else:
            self.cache = NullExtensibleCache()

        if env is None:
            env = StandardEnvironment()
        self.env = env
        env.initialize(self)

        stats = env.stats
        stats.registerTimer('SiteConfigLoad')
        stats.registerTimer('PageLoad')
        stats.registerTimer("BuildRenderData")
        stats.registerTimer("BuildLazyPageData")
        stats.registerTimer("PageRender")
        stats.registerTimer("PageRenderSegments")
        stats.registerTimer("PageRenderLayout")
        stats.registerTimer("PageSerialize")
        stats.registerCounter('PageLoads')
        stats.registerCounter('PageRenderSegments')
        stats.registerCounter('PageRenderLayout')

    @cached_property
    def config(self):
        logger.debug("Creating site configuration...")
        start_time = time.perf_counter()

        if not self.theme_site:
            path = os.path.join(self.root_dir, CONFIG_PATH)
        else:
            path = os.path.join(self.root_dir, THEME_CONFIG_PATH)

        theme_path = None
        if not self.theme_site and self.theme_dir:
            theme_path = os.path.join(self.theme_dir, THEME_CONFIG_PATH)

        config_cache = self.cache.getCache('app')
        config = PieCrustConfiguration(
            path=path, theme_path=theme_path,
            cache=config_cache, theme_config=self.theme_site)

        local_path = os.path.join(
            self.root_dir, 'configs', 'local.yml')
        config.addVariant(local_path, raise_if_not_found=False)

        if self.theme_site:
            variant_path = os.path.join(
                self.root_dir, 'configs', 'theme_preview.yml')
            config.addVariant(variant_path, raise_if_not_found=False)

        self.env.stats.stepTimer('SiteConfigLoad',
                                 time.perf_counter() - start_time)
        return config

    @cached_property
    def assets_dirs(self):
        assets_dirs = self._get_configurable_dirs(
            ASSETS_DIR, 'site/assets_dirs')

        # Also add the theme directory, if any.
        if self.theme_dir:
            default_theme_dir = os.path.join(self.theme_dir, ASSETS_DIR)
            if os.path.isdir(default_theme_dir):
                assets_dirs.append(default_theme_dir)

        return assets_dirs

    @cached_property
    def templates_dirs(self):
        templates_dirs = self._get_configurable_dirs(
            TEMPLATES_DIR, 'site/templates_dirs')

        # Also, add the theme directory, if any.
        if self.theme_dir:
            default_theme_dir = os.path.join(self.theme_dir, TEMPLATES_DIR)
            if os.path.isdir(default_theme_dir):
                templates_dirs.append(default_theme_dir)

        return templates_dirs

    @cached_property
    def theme_dir(self):
        # No theme if the curent site is already a theme.
        if self.theme_site:
            return None

        # See if there's a theme we absolutely want.
        td = os.path.join(self.root_dir, THEME_DIR)
        if os.path.isdir(td):
            return td

        # Try to load a theme specified in the configuration.
        from piecrust.themes.base import ThemeLoader
        loader = ThemeLoader(self.root_dir)
        theme_dir = loader.getThemeDir()
        if theme_dir is not None:
            return theme_dir

        # Nothing... use the default theme.
        return os.path.join(RESOURCES_DIR, 'theme')

    @cached_property
    def plugins_dirs(self):
        return self._get_configurable_dirs(PLUGINS_DIR, 'site/plugins_dirs')

    @cached_property
    def cache_dir(self):
        return os.path.join(self.root_dir, CACHE_DIR, self.cache_key)

    @cached_property
    def sources(self):
        defs = {}
        for cls in self.plugin_loader.getSources():
            defs[cls.SOURCE_NAME] = cls

        sources = []
        for n, s in self.config.get('site/sources').items():
            cls = defs.get(s['type'])
            if cls is None:
                raise ConfigurationError("No such page source type: %s" %
                                         s['type'])
            src = cls(self, n, s)
            sources.append(src)

        return sources

    @cached_property
    def routes(self):
        routes = []
        for r in self.config.get('site/routes'):
            rte = Route(self, r)
            routes.append(rte)
        routes = sorted(routes, key=lambda r: r.pass_num)
        return routes

    @cached_property
    def publishers(self):
        defs_by_name = {}
        defs_by_scheme = {}
        for cls in self.plugin_loader.getPublishers():
            defs_by_name[cls.PUBLISHER_NAME] = cls
            if cls.PUBLISHER_SCHEME:
                defs_by_scheme[cls.PUBLISHER_SCHEME] = cls

        tgts = []
        publish_config = self.config.get('publish')
        if publish_config is None:
            return tgts

        for n, t in publish_config.items():
            pub_class = None
            if isinstance(t, dict):
                pub_type = t.get('type')
                pub_class = defs_by_name[pub_type]
                pub_cfg = t
            elif isinstance(t, str):
                comps = urllib.parse.urlparse(t)
                pub_type = comps.scheme
                pub_class = defs_by_scheme[pub_type]
                pub_cfg = None
            if pub_class is None:
                raise ConfigurationError("No such publisher: %s" % pub_type)

            tgt = pub_class(self, n, pub_cfg)
            if pub_cfg is None:
                tgt.parseUrlTarget(comps)

            tgts.append(tgt)
        return tgts

    def getSource(self, source_name):
        for source in self.sources:
            if source.name == source_name:
                return source

        from piecrust.sources.base import SourceNotFoundError
        raise SourceNotFoundError(source_name)

    def getSourceRoute(self, source_name):
        for route in self.routes:
            if route.source_name == source_name:
                return route

        from piecrust.routing import RouteNotFoundError
        raise RouteNotFoundError(source_name)

    def getPublisher(self, target_name):
        for pub in self.publishers:
            if pub.target == target_name:
                return pub
        return None

    def getPage(self, source, content_item):
        cache_key = '%s@%s' % (source.name, content_item.spec)
        return self.env.page_repository.get(
            cache_key,
            lambda: Page(source, content_item))

    def resolvePath(self, path):
        path = multi_replace(path, {'%theme_dir%': self.theme_dir})
        return os.path.join(self.root_dir, path)

    def _get_configurable_dirs(self, default_rel_dir, conf_name):
        dirs = []

        # Add custom directories from the configuration.
        conf_dirs = self.config.get(conf_name)
        if conf_dirs is not None:
            if isinstance(conf_dirs, str):
                dirs.append(self.resolvePath(conf_dirs))
            else:
                dirs += [self.resolvePath(p) for p in conf_dirs]

        # Add the default directory if it exists.
        default_dir = os.path.join(self.root_dir, default_rel_dir)
        if os.path.isdir(default_dir):
            dirs.append(default_dir)

        return dirs


def apply_variants_and_values(app, config_variants=None, config_values=None):
    if config_variants is not None:
        for value in config_variants:
            logger.debug("Adding configuration variant '%s'." % value)
            variant_path = os.path.join(
                app.root_dir, 'configs', '%s.yml' % value)
            app.config.addVariant(variant_path)

    if config_values is not None:
        for name, value in config_values:
            logger.debug("Adding configuration override '%s': %s" %
                         (name, value))
            app.config.addVariantValue(name, value)


class PieCrustFactory(object):
    """ A class that builds a PieCrust app instance.
    """
    def __init__(
            self, root_dir, *,
            cache=True, cache_key=None,
            config_variants=None, config_values=None,
            debug=False, theme_site=False):
        self.root_dir = root_dir
        self.cache = cache
        self.cache_key = cache_key
        self.config_variants = config_variants
        self.config_values = config_values
        self.debug = debug
        self.theme_site = theme_site

    def create(self):
        app = PieCrust(
            self.root_dir,
            cache=self.cache,
            cache_key=self.cache_key,
            debug=self.debug,
            theme_site=self.theme_site)
        apply_variants_and_values(
            app, self.config_variants, self.config_values)
        return app

