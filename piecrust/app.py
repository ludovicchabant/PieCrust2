import json
import os.path
import types
import codecs
import hashlib
import logging
import yaml
from cache import SimpleCache
from decorators import lazy_property
from plugins import PluginLoader
from environment import StandardEnvironment
from configuration import Configuration, merge_dicts


APP_VERSION = '2.0.0alpha'
CACHE_VERSION = '2.0'

CACHE_DIR = '_cache'
TEMPLATES_DIR = '_content/templates'
PAGES_DIR = '_content/pages'
POSTS_DIR = '_content/posts'
PLUGINS_DIR = '_content/plugins'
THEME_DIR = '_content/theme'

CONFIG_PATH = '_content/config.yml'
THEME_CONFIG_PATH = '_content/theme_config.yml'


logger = logging.getLogger(__name__)


class VariantNotFoundError(Exception):
    def __init__(self, variant_path, message=None):
        super(VariantNotFoundError, self).__init__(
                message or ("No such configuration variant: %s" % variant_path))


class PieCrustConfiguration(Configuration):
    def __init__(self, paths=None, cache_dir=False):
        super(PieCrustConfiguration, self).__init__()
        self.paths = paths
        self.cache_dir = cache_dir
        self.fixups = []

    def applyVariant(self, variant_path, raise_if_not_found=True):
        variant = self.get(variant_path)
        if variant is None:
            if raise_if_not_found:
                raise VariantNotFoundError(variant_path)
            return
        if not isinstance(variant, dict):
            raise VariantNotFoundError(variant_path,
                    "Configuration variant '%s' is not an array. "
                    "Check your configuration file." % variant_path)
        self.merge(variant)

    def _load(self):
        if self.paths is None:
            self._values = self._validateAll({})
            return
        
        path_times = filter(self.paths,
                lambda p: os.path.getmtime(p))
        cache_key = hashlib.md5("version=%s&cache=%s" % (
                APP_VERSION, CACHE_VERSION))
        
        cache = None
        if self.cache_dir:
            cache = SimpleCache(self.cache_dir)

        if cache is not None:
            if cache.isValid('config.json', path_times):
                config_text = cache.read('config.json')
                self._values = json.loads(config_text)
                
                actual_cache_key = self._values.get('__cache_key')
                if actual_cache_key == cache_key:
                    return

        values = {}
        for i, p in enumerate(self.paths):
            with codecs.open(p, 'r', 'utf-8') as fp:
                loaded_values = yaml.load(fp.read())
            for fixup in self.fixups:
                fixup(i, loaded_values)
            merge_dicts(values, loaded_values)

        for fixup in self.fixups:
            fixup(len(self.paths), values)

        self._values = self._validateAll(values)

        if cache is not None:
            self._values['__cache_key'] = cache_key
            config_text = json.dumps(self._values)
            cache.write('config.json', config_text)


class PieCrust(object):
    def __init__(self, root, cache=True, debug=False, env=None):
        self.root = root
        self.debug = debug
        self.cache = cache
        self.plugin_loader = PluginLoader(self)
        self.env = env
        if self.env is None:
            self.env = StandardEnvironment()
        self.env.initialize(self)

    @lazy_property
    def config(self):
        logger.debug("Loading site configuration...")
        paths = []
        if self.theme_dir:
            paths.append(os.path.join(self.theme_dir, THEME_CONFIG_PATH))
        paths.append(os.path.join(self.root, CONFIG_PATH))

        config = PieCrustConfiguration(paths, self.cache_dir)
        if self.theme_dir:
            # We'll need to patch the templates directories to be relative
            # to the site's root, and not the theme root.
            def _fixupThemeTemplatesDir(index, config):
                if index == 0:
                    sitec = config.get('site')
                    if sitec:
                        tplc = sitec.get('templates_dirs')
                        if tplc:
                            if isinstance(tplc, types.StringTypes):
                                tplc = [tplc]
                            sitec['templates_dirs'] = filter(tplc,
                                    lambda p: os.path.join(self.theme_dir, p))

            config.fixups.append(_fixupThemeTemplatesDir)

        return config

    @lazy_property
    def templates_dirs(self):
        templates_dirs = self._get_configurable_dirs(TEMPLATES_DIR,
                'site/templates_dirs')

        # Also, add the theme directory, if nay.
        if self.theme_dir:
            default_theme_dir = os.path.join(self.theme_dir, TEMPLATES_DIR)
            if os.path.isdir(default_theme_dir):
                templates_dirs.append(default_theme_dir)

        return templates_dirs

    @lazy_property
    def pages_dir(self):
        return self._get_dir(PAGES_DIR)

    @lazy_property
    def posts_dir(self):
        return self._get_dir(POSTS_DIR)

    @lazy_property
    def plugins_dirs(self):
        return self._get_configurable_dirs(PLUGINS_DIR,
                'site/plugins_dirs')

    @lazy_property
    def theme_dir(self):
        return self._get_dir(THEME_DIR)

    @lazy_property
    def cache_dir(self):
        if self.cache:
            return os.path.join(self.root, CACHE_DIR)
        return False

    def _get_dir(self, default_rel_dir):
        abs_dir = os.path.join(self.root, default_rel_dir)
        if os.path.isdir(abs_dir):
            return abs_dir
        return False

    def _get_configurable_dirs(self, default_rel_dir, conf_name):
        dirs = []

        # Add custom directories from the configuration.
        conf_dirs = self.config.get(conf_name)
        if conf_dirs is not None:
            dirs += filter(conf_dirs,
                    lambda p: os.path.join(self.root, p))

        # Add the default directory if it exists.
        default_dir = os.path.join(self.root, default_rel_dir)
        if os.path.isdir(default_dir):
            dirs.append(default_dir)

        return dirs

