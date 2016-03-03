import time
import os.path
import hashlib
import logging
from werkzeug.utils import cached_property
from piecrust import (
        RESOURCES_DIR,
        CACHE_DIR, TEMPLATES_DIR, ASSETS_DIR,
        THEME_DIR,
        CONFIG_PATH, THEME_CONFIG_PATH)
from piecrust.appconfig import PieCrustConfiguration
from piecrust.cache import ExtensibleCache, NullExtensibleCache
from piecrust.plugins.base import PluginLoader
from piecrust.environment import StandardEnvironment
from piecrust.configuration import ConfigurationError
from piecrust.routing import Route
from piecrust.sources.base import REALM_THEME
from piecrust.taxonomies import Taxonomy


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

        self.env = env
        if self.env is None:
            self.env = StandardEnvironment()
        self.env.initialize(self)
        self.env.registerTimer('SiteConfigLoad')
        self.env.registerTimer('PageLoad')
        self.env.registerTimer("PageDataBuild")
        self.env.registerTimer("BuildRenderData")
        self.env.registerTimer("PageRender")
        self.env.registerTimer("PageRenderSegments")
        self.env.registerTimer("PageRenderLayout")
        self.env.registerTimer("PageSerialize")

    @cached_property
    def config(self):
        logger.debug("Creating site configuration...")
        start_time = time.perf_counter()

        paths = []
        if not self.theme_site:
            if self.theme_dir:
                paths.append(os.path.join(self.theme_dir, THEME_CONFIG_PATH))
            paths.append(os.path.join(self.root_dir, CONFIG_PATH))
        else:
            paths.append(os.path.join(self.root_dir, THEME_CONFIG_PATH))
            preview_path = os.path.join(
                    self.root_dir, 'configs', 'theme_preview.yml')
            if os.path.isfile(preview_path):
                paths.append(preview_path)

        config_cache = self.cache.getCache('app')
        config = PieCrustConfiguration(paths, config_cache,
                                       theme_config=self.theme_site)
        if self.theme_dir:
            # We'll need to flag all page sources as coming from
            # the theme.
            def _fixupThemeSources(index, config):
                if index != 0:
                    return
                sitec = config.get('site')
                if sitec is None:
                    sitec = {}
                    config['site'] = sitec
                srcc = sitec.get('sources')
                if srcc is not None:
                    for sn, sc in srcc.items():
                        sc['realm'] = REALM_THEME
            config.addFixup(_fixupThemeSources)

        self.env.stepTimer('SiteConfigLoad', time.perf_counter() - start_time)
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
        if self.theme_site:
            return None
        td = self._get_dir(THEME_DIR)
        if td is not None:
            return td
        return os.path.join(RESOURCES_DIR, 'theme')

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
        return routes

    @cached_property
    def taxonomies(self):
        taxonomies = []
        for tn, tc in self.config.get('site/taxonomies').items():
            tax = Taxonomy(self, tn, tc)
            taxonomies.append(tax)
        return taxonomies

    def getSource(self, source_name):
        for source in self.sources:
            if source.name == source_name:
                return source
        return None

    def getRoutes(self, source_name, *, skip_taxonomies=False):
        for route in self.routes:
            if route.source_name == source_name:
                if not skip_taxonomies or route.taxonomy_name is None:
                    yield route

    def getRoute(self, source_name, route_metadata, *, skip_taxonomies=False):
        for route in self.getRoutes(source_name,
                                    skip_taxonomies=skip_taxonomies):
            if (route_metadata is None or
                    route.matchesMetadata(route_metadata)):
                return route
        return None

    def getTaxonomyRoute(self, tax_name, source_name):
        for route in self.routes:
            if (route.taxonomy_name == tax_name and
                    route.source_name == source_name):
                return route
        return None

    def getTaxonomy(self, tax_name):
        for tax in self.taxonomies:
            if tax.name == tax_name:
                return tax
        return None

    def _get_dir(self, default_rel_dir):
        abs_dir = os.path.join(self.root_dir, default_rel_dir)
        if os.path.isdir(abs_dir):
            return abs_dir
        return None

    def _get_configurable_dirs(self, default_rel_dir, conf_name):
        dirs = []

        # Add custom directories from the configuration.
        conf_dirs = self.config.get(conf_name)
        if conf_dirs is not None:
            if isinstance(conf_dirs, str):
                dirs.append(os.path.join(self.root_dir, conf_dirs))
            else:
                dirs += [os.path.join(self.root_dir, p) for p in conf_dirs]

        # Add the default directory if it exists.
        default_dir = os.path.join(self.root_dir, default_rel_dir)
        if os.path.isdir(default_dir):
            dirs.append(default_dir)

        return dirs



def apply_variant_and_values(app, config_variant=None, config_values=None):
    if config_variant is not None:
        logger.debug("Adding configuration variant '%s'." % config_variant)
        variant_path = os.path.join(
                app.root_dir, 'configs', '%s.yml' % config_variant)
        app.config.addVariant(variant_path)

    if config_values is not None:
        for name, value in config_values:
            logger.debug("Adding configuration override '%s': %s" % (name, value))
            app.config.addVariantValue(name, value)


class PieCrustFactory(object):
    def __init__(
            self, root_dir, *,
            cache=True, cache_key=None,
            config_variant=None, config_values=None,
            debug=False, theme_site=False):
        self.root_dir = root_dir
        self.cache = cache
        self.cache_key = cache_key
        self.config_variant = config_variant
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
        apply_variant_and_values(
                app, self.config_variant, self.config_values)
        return app

