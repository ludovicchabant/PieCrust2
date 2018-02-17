import re
import os.path
import copy
import json
import urllib
import logging
import hashlib
import collections
import yaml
from piecrust import APP_VERSION, CACHE_VERSION, DEFAULT_DATE_FORMAT
from piecrust.appconfigdefaults import (
    default_configuration,
    default_theme_content_model_base,
    default_content_model_base,
    get_default_content_model, get_default_content_model_for_blog)
from piecrust.cache import NullCache
from piecrust.configuration import (
    Configuration, ConfigurationError, ConfigurationLoader,
    try_get_dict_values, set_dict_value,
    merge_dicts, visit_dict)
from piecrust.sources.base import REALM_USER, REALM_THEME


logger = logging.getLogger(__name__)


class InvalidConfigurationPathError(Exception):
    pass


class VariantNotFoundError(Exception):
    def __init__(self, variant_name, message=None):
        super(VariantNotFoundError, self).__init__(
            message or ("No such configuration variant: %s" %
                        variant_name))


class PieCrustConfiguration(Configuration):
    def __init__(self, *, path=None, theme_path=None, values=None,
                 cache=None, validate=True, theme_config=False):
        if theme_config and theme_path:
            raise Exception("Can't be a theme site config and still have a "
                            "theme applied.")
        super(PieCrustConfiguration, self).__init__()
        self._path = path
        self._theme_path = theme_path
        self._cache = cache or NullCache()
        self._cache_hash_mod = ''
        self._custom_paths = []
        self._post_fixups = []
        self.theme_config = theme_config
        # Set the values after we set the rest, since our validation needs
        # our attributes.
        if values is not None:
            self.setAll(values, validate=validate)

    def addPath(self, p):
        if not p:
            raise InvalidConfigurationPathError()
        self._ensureNotLoaded()
        self._custom_paths.append(p)

    def addVariant(self, variant_path, raise_if_not_found=True):
        self._ensureNotLoaded()
        if os.path.isfile(variant_path):
            self.addPath(variant_path)
        elif raise_if_not_found:
            logger.error(
                "Configuration variants should now be `.yml` files "
                "located in the `configs/` directory of your website.")
            raise VariantNotFoundError(variant_path)

    def addVariantValue(self, path, value):
        def _fixup(config):
            set_dict_value(config, path, value)

        self._post_fixups.append(_fixup)
        self._cache_hash_mod += '&val[%s=%s]' % (path, repr(value))

    def setAll(self, values, validate=False):
        # Override base class implementation
        values = self._processConfigs({}, values)
        if validate:
            values = self._validateAll(values)
        self._values = values

    def _ensureNotLoaded(self):
        if self._values is not None:
            raise Exception("The configurations has been loaded.")

    def _load(self):
        # Figure out where to load this configuration from.
        paths = []
        if self._theme_path:
            paths.append(self._theme_path)
        if self._path:
            paths.append(self._path)
        paths += self._custom_paths

        # Build the cache-key.
        path_times = [os.path.getmtime(p) for p in paths]
        cache_key_hash = hashlib.md5(
            ("version=%s&cache=%d" % (
                APP_VERSION, CACHE_VERSION)).encode('utf8'))
        for p in paths:
            cache_key_hash.update(("&path=%s" % p).encode('utf8'))
        if self._cache_hash_mod:
            cache_key_hash.update(self._cache_hash_mod.encode('utf8'))
        cache_key = cache_key_hash.hexdigest()

        # Check the cache for a valid version.
        if path_times and self._cache.isValid('config.json', path_times):
            logger.debug("Loading configuration from cache...")
            config_text = self._cache.read('config.json')
            self._values = json.loads(
                config_text,
                object_pairs_hook=collections.OrderedDict)

            actual_cache_key = self._values.get('__cache_key')
            if actual_cache_key == cache_key:
                # The cached version has the same key! Awesome!
                self._values['__cache_valid'] = True
                return
            logger.debug("Outdated cache key '%s' (expected '%s')." % (
                actual_cache_key, cache_key))

        # Nope, load from the paths.
        try:
            # Theme values.
            theme_values = None
            if self._theme_path:
                logger.debug("Loading theme layer from: %s" % self._theme_path)
                theme_values = self._loadFrom(self._theme_path)

            # Site and variant values.
            site_paths = []
            if self._path:
                site_paths.append(self._path)
            site_paths += self._custom_paths

            site_values = {}
            for path in site_paths:
                logger.debug("Loading config layer from: %s" % path)
                cur_values = self._loadFrom(path)
                merge_dicts(site_values, cur_values)

            # Do it!
            values = self._processConfigs(theme_values, site_values)
            self._values = self._validateAll(values)
        except Exception as ex:
            logger.exception(ex)
            raise Exception(
                "Error loading configuration from: %s" %
                ', '.join(paths)) from ex

        logger.debug("Caching configuration...")
        self._values['__cache_key'] = cache_key
        config_text = json.dumps(self._values)
        self._cache.write('config.json', config_text)

        self._values['__cache_valid'] = False

    def _loadFrom(self, path):
        logger.debug("Loading configuration from: %s" % path)
        with open(path, 'r', encoding='utf-8') as fp:
            values = yaml.load(
                fp.read(),
                Loader=ConfigurationLoader)
        if values is None:
            values = {}
        return values

    def _processConfigs(self, theme_values, site_values):
        # Start with the default configuration.
        values = copy.deepcopy(default_configuration)

        # If we have a theme, apply the theme on that. So stuff like routes
        # will now look like:
        # [custom theme] + [default theme] + [default]
        if theme_values is not None:
            self._processThemeLayer(theme_values, values)

        # Make all sources belong to the "theme" realm at this point.
        srcc = values['site'].get('sources')
        if srcc:
            for sn, sc in srcc.items():
                sc['realm'] = REALM_THEME

        # Now we apply the site stuff. We want to end up with:
        # [custom site] + [default site] + [custom theme] + [default theme] +
        #   [default]
        if site_values is not None:
            self._processSiteLayer(site_values, values)

        # Set the theme site flag.
        if self.theme_config:
            values['site']['theme_site'] = True

        # Run final fixups
        if self._post_fixups:
            logger.debug("Applying %d configuration fixups." %
                         len(self._post_fixups))
            for f in self._post_fixups:
                f(values)

        return values

    def _processThemeLayer(self, theme_values, values):
        # Generate the default theme model.
        gen_default_theme_model = bool(try_get_dict_values(
            (theme_values, 'site/use_default_theme_content'),
            default=True))
        if gen_default_theme_model:
            logger.debug("Generating default theme content model...")
            cc = copy.deepcopy(default_theme_content_model_base)
            merge_dicts(values, cc)

        # Merge the theme config into the result config.
        merge_dicts(values, theme_values)

    def _processSiteLayer(self, site_values, values):
        # Default site content.
        gen_default_site_model = bool(try_get_dict_values(
            (site_values, 'site/use_default_content'),
            (values, 'site/use_default_content'),
            default=True))
        if gen_default_site_model:
            logger.debug("Generating default content model...")
            cc = copy.deepcopy(default_content_model_base)
            merge_dicts(values, cc)

            dcm = get_default_content_model(site_values, values)
            merge_dicts(values, dcm)

            blogsc = try_get_dict_values(
                (site_values, 'site/blogs'),
                (values, 'site/blogs'))
            if blogsc is None:
                blogsc = ['posts']
                set_dict_value(site_values, 'site/blogs', blogsc)

            is_only_blog = (len(blogsc) == 1)
            for blog_name in reversed(blogsc):
                blog_cfg = get_default_content_model_for_blog(
                    blog_name, is_only_blog, site_values, values,
                    theme_site=self.theme_config)
                merge_dicts(values, blog_cfg)

        # Merge the site config into the result config.
        merge_dicts(values, site_values)

    def _validateAll(self, values):
        if values is None:
            values = {}

        # Add a section for our cached information, and start visiting
        # the configuration tree, calling validation functions as we
        # find them.
        cachec = collections.OrderedDict()
        values['__cache'] = cachec
        cache_writer = _ConfigCacheWriter(cachec)
        globs = globals()

        def _visitor(path, val, parent_val, parent_key):
            callback_name = '_validate_' + path.replace('/', '_')
            callback = globs.get(callback_name)
            if callback:
                try:
                    val2 = callback(val, values, cache_writer)
                except Exception as ex:
                    logger.exception(ex)
                    raise Exception("Error raised in validator '%s'." %
                                    callback_name) from ex
                if val2 is None:
                    raise Exception("Validator '%s' isn't returning a "
                                    "coerced value." % callback_name)
                parent_val[parent_key] = val2

        visit_dict(values, _visitor)

        return values


class _ConfigCacheWriter(object):
    def __init__(self, cache_dict):
        self._cache_dict = cache_dict

    def write(self, name, val):
        logger.debug("Caching configuration item '%s' = %s" % (name, val))
        self._cache_dict[name] = val


# Configuration value validators.
#
# Make sure we have basic site stuff.
def _validate_site(v, values, cache):
    sources = v.get('sources')
    if not sources:
        raise ConfigurationError("No sources were defined.")
    routes = v.get('routes')
    if not routes:
        raise ConfigurationError("No routes were defined.")
    taxonomies = v.get('taxonomies')
    if taxonomies is None:
        v['taxonomies'] = {}
    return v


# Make sure the site root ends with a slash.
def _validate_site_root(v, values, cache):
    url_bits = urllib.parse.urlparse(v)
    if url_bits.params or url_bits.query or url_bits.fragment:
        raise ConfigurationError("Root URL is invalid: %s" % v)

    path = url_bits.path.rstrip('/') + '/'
    if '%' not in path:
        path = urllib.parse.quote(path)

    root_url = urllib.parse.urlunparse((
        url_bits.scheme, url_bits.netloc, path, '', '', ''))
    return root_url


# Cache auto-format regexes, check that `.html` is in there.
def _validate_site_auto_formats(v, values, cache):
    if not isinstance(v, dict):
        raise ConfigurationError("The 'site/auto_formats' setting must be "
                                 "a dictionary.")

    v.setdefault('html', values['site']['default_format'])
    auto_formats_re = r"\.(%s)$" % (
        '|'.join(
            [re.escape(i) for i in list(v.keys())]))
    cache.write('auto_formats_re', auto_formats_re)
    return v


# Check that the default auto-format is known.
def _validate_site_default_auto_format(v, values, cache):
    if v not in values['site']['auto_formats']:
        raise ConfigurationError(
            "Default auto-format '%s' is not declared." % v)
    return v


# Cache pagination suffix regex and format.
def _validate_site_pagination_suffix(v, values, cache):
    if len(v) == 0 or v[0] != '/':
        raise ConfigurationError("The 'site/pagination_suffix' setting "
                                 "must start with a slash.")
    if '%num%' not in v:
        raise ConfigurationError("The 'site/pagination_suffix' setting "
                                 "must contain the '%num%' placeholder.")

    pgn_suffix_fmt = v.replace('%num%', '%(num)d')
    cache.write('pagination_suffix_format', pgn_suffix_fmt)

    pgn_suffix_re = re.escape(v)
    pgn_suffix_re = (pgn_suffix_re.replace("\\%num\\%", "(?P<num>\\d+)") +
                     '$')
    cache.write('pagination_suffix_re', pgn_suffix_re)
    return v


# Make sure theme sources is a list.
def _validate_site_theme_sources(v, values, cache):
    if not isinstance(v, list):
        v = [v]
    return v


def _validate_site_sources(v, values, cache):
    # Basic checks.
    if not v:
        raise ConfigurationError("There are no sources defined.")
    if not isinstance(v, dict):
        raise ConfigurationError("The 'site/sources' setting must be a "
                                 "dictionary.")

    # Sources have the `default` scanner by default, duh. Also, a bunch
    # of other default values for other configuration stuff.
    reserved_endpoints = set(['piecrust', 'site', 'page', 'route',
                              'assets', 'pagination', 'siblings',
                              'family'])
    for sn, sc in v.items():
        if not isinstance(sc, dict):
            raise ConfigurationError("All sources in 'site/sources' must "
                                     "be dictionaries.")
        sc.setdefault('type', 'default')
        sc.setdefault('fs_endpoint', sn)
        sc.setdefault('ignore_missing_dir', False)
        sc.setdefault('data_endpoint', None)
        sc.setdefault('data_type', None)
        sc.setdefault('default_layout', 'default')
        sc.setdefault('item_name', sn)
        sc.setdefault('items_per_page', 5)
        sc.setdefault('date_format', DEFAULT_DATE_FORMAT)
        sc.setdefault('realm', REALM_USER)
        sc.setdefault('pipeline', None)

        # Validate endpoints.
        endpoint = sc['data_endpoint']
        if endpoint in reserved_endpoints:
            raise ConfigurationError(
                "Source '%s' is using a reserved endpoint name: %s" %
                (sn, endpoint))

    return v


def _validate_site_routes(v, values, cache):
    if not v:
        raise ConfigurationError("There are no routes defined.")
    if not isinstance(v, list):
        raise ConfigurationError("The 'site/routes' setting must be a "
                                 "list.")

    # Check routes are referencing correct sources, have default
    # values, etc.
    used_sources = set()
    source_configs = values['site']['sources']
    existing_sources = set(source_configs.keys())
    for rc in v:
        if not isinstance(rc, dict):
            raise ConfigurationError("All routes in 'site/routes' must be "
                                     "dictionaries.")
        rc_url = rc.get('url')
        if not rc_url:
            raise ConfigurationError("All routes in 'site/routes' must "
                                     "have an 'url'.")
        if rc_url[0] != '/':
            raise ConfigurationError("Route URLs must start with '/'.")

        r_source = rc.get('source')
        if r_source is None:
            raise ConfigurationError("Routes must specify a source.")
        if r_source not in existing_sources:
            raise ConfigurationError("Route is referencing unknown "
                                     "source: %s" % r_source)
        if r_source in used_sources:
            raise ConfigurationError("Source '%s' already has a route." %
                                     r_source)
        used_sources.add(r_source)

        rc.setdefault('pass', 1)
        rc.setdefault('page_suffix', '/%num%')

    # Raise errors about non-asset sources that have no URL routes.
    sources_with_no_route = list(filter(
        lambda s: source_configs[s].get('pipeline') != 'asset',
        existing_sources.difference(used_sources)))
    if sources_with_no_route:
        raise ConfigurationError(
            "The following sources have no routes: %s" %
            ', '.join(sources_with_no_route))

    return v


def _validate_site_taxonomies(v, values, cache):
    if not isinstance(v, dict):
        raise ConfigurationError(
            "The 'site/taxonomies' setting must be a mapping.")
    for tn, tc in v.items():
        tc.setdefault('multiple', False)
        tc.setdefault('term', tn)
        tc.setdefault('page', '_%s.%%ext%%' % tc['term'])
    return v


def _validate_site_plugins(v, values, cache):
    if isinstance(v, str):
        v = v.split(',')
    elif not isinstance(v, list):
        raise ConfigurationError(
            "The 'site/plugins' setting must be an array, or a "
            "comma-separated list.")
    return v

