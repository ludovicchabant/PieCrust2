import re
import os.path
import copy
import json
import urllib
import logging
import hashlib
import collections
import yaml
from piecrust import (
        APP_VERSION, CACHE_VERSION,
        DEFAULT_FORMAT, DEFAULT_TEMPLATE_ENGINE, DEFAULT_POSTS_FS,
        DEFAULT_DATE_FORMAT, DEFAULT_THEME_SOURCE)
from piecrust.cache import NullCache
from piecrust.configuration import (
        Configuration, ConfigurationError, ConfigurationLoader,
        get_dict_value, set_dict_value, merge_dicts, visit_dict)
from piecrust.sources.base import REALM_USER, REALM_THEME


logger = logging.getLogger(__name__)


class VariantNotFoundError(Exception):
    def __init__(self, variant_name, message=None):
        super(VariantNotFoundError, self).__init__(
                message or ("No such configuration variant: %s" %
                            variant_name))


def _make_variant_fixup(variant_name, raise_if_not_found):
    def _variant_fixup(index, config):
        if index != -1:
            return
        try:
            try:
                v = get_dict_value(config, 'variants/%s' % variant_name)
            except KeyError:
                raise VariantNotFoundError(variant_name)
            if not isinstance(v, dict):
                raise VariantNotFoundError(
                        variant_name,
                        "Configuration variant '%s' is not an array. "
                        "Check your configuration file." % variant_name)
            merge_dicts(config, v)
        except VariantNotFoundError:
            if raise_if_not_found:
                raise

    return _variant_fixup


class PieCrustConfiguration(Configuration):
    def __init__(self, paths=None, cache=None, values=None, validate=True,
                 theme_config=False):
        super(PieCrustConfiguration, self).__init__()
        self._paths = paths
        self._cache = cache or NullCache()
        self._fixups = []
        self.theme_config = theme_config
        # Set the values after we set the rest, since our validation needs
        # our attributes.
        if values:
            self.setAll(values, validate=validate)

    def addFixup(self, f):
        self._ensureNotLoaded()
        self._fixups.append(f)

    def addPath(self, p, first=False):
        self._ensureNotLoaded()
        if not first:
            self._paths.append(p)
        else:
            self._paths.insert(0, p)

    def addVariant(self, variant_path, raise_if_not_found=True):
        self._ensureNotLoaded()
        if os.path.isfile(variant_path):
            self.addPath(variant_path)
        else:
            name, _ = os.path.splitext(os.path.basename(variant_path))
            fixup = _make_variant_fixup(name, raise_if_not_found)
            self.addFixup(fixup)

            logger.warning(
                "Configuration variants should now be `.yml` files located "
                "in the `configs/` directory of your website.")
            logger.warning(
                "Variants defined in the site configuration will be "
                "deprecated in a future version of PieCrust.")

    def addVariantValue(self, path, value):
        def _fixup(index, config):
            set_dict_value(config, path, value)
        self.addFixup(_fixup)

    def _ensureNotLoaded(self):
        if self._values is not None:
            raise Exception("The configurations has been loaded.")

    def _load(self):
        if self._paths is None:
            self._values = self._validateAll({})
            return

        path_times = [os.path.getmtime(p) for p in self._paths]

        cache_key_hash = hashlib.md5(
                ("version=%s&cache=%d" % (
                    APP_VERSION, CACHE_VERSION)).encode('utf8'))
        for p in self._paths:
            cache_key_hash.update(("&path=%s" % p).encode('utf8'))
        cache_key = cache_key_hash.hexdigest()

        if self._cache.isValid('config.json', path_times):
            logger.debug("Loading configuration from cache...")
            config_text = self._cache.read('config.json')
            self._values = json.loads(
                    config_text,
                    object_pairs_hook=collections.OrderedDict)

            actual_cache_key = self._values.get('__cache_key')
            if actual_cache_key == cache_key:
                self._values['__cache_valid'] = True
                return
            logger.debug("Outdated cache key '%s' (expected '%s')." % (
                    actual_cache_key, cache_key))

        logger.debug("Loading configuration from: %s" % self._paths)
        values = {}
        try:
            for i, p in enumerate(self._paths):
                with open(p, 'r', encoding='utf-8') as fp:
                    loaded_values = yaml.load(
                            fp.read(),
                            Loader=ConfigurationLoader)
                if loaded_values is None:
                    loaded_values = {}
                for fixup in self._fixups:
                    fixup(i, loaded_values)
                merge_dicts(values, loaded_values)

            for fixup in self._fixups:
                fixup(-1, values)

            self._values = self._validateAll(values)
        except Exception as ex:
            raise Exception("Error loading configuration from: %s" %
                            ', '.join(self._paths)) from ex

        logger.debug("Caching configuration...")
        self._values['__cache_key'] = cache_key
        config_text = json.dumps(self._values)
        self._cache.write('config.json', config_text)

        self._values['__cache_valid'] = False

    def _validateAll(self, values):
        if values is None:
            values = {}

        # Add the loaded values to the default configuration.
        values = merge_dicts(copy.deepcopy(default_configuration), values)

        # Set the theme site flag.
        if self.theme_config:
            values['site']['theme_site'] = True

        # Figure out if we need to generate the configuration for the
        # default content model.
        sitec = values.setdefault('site', {})
        if (
                ('sources' not in sitec and
                 'routes' not in sitec and
                 'taxonomies' not in sitec) or
                sitec.get('use_default_content')):
            logger.debug("Generating default content model...")
            values = self._generateDefaultContentModel(values)

        # Add a section for our cached information.
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
                    raise Exception("Error raised in validator '%s'." %
                                    callback_name) from ex
                if val2 is None:
                    raise Exception("Validator '%s' isn't returning a "
                                    "coerced value." % callback_name)
                parent_val[parent_key] = val2

        visit_dict(values, _visitor)

        return values

    def _generateDefaultContentModel(self, values):
        dcmcopy = copy.deepcopy(default_content_model_base)
        values = merge_dicts(dcmcopy, values)

        blogsc = values['site'].get('blogs')
        if blogsc is None:
            blogsc = ['posts']
            values['site']['blogs'] = blogsc

        is_only_blog = (len(blogsc) == 1)
        for blog_name in blogsc:
            blog_cfg = get_default_content_model_for_blog(
                    blog_name, is_only_blog, values,
                    theme_site=self.theme_config)
            values = merge_dicts(blog_cfg, values)

        dcm = get_default_content_model(values)
        values = merge_dicts(dcm, values)

        return values


class _ConfigCacheWriter(object):
    def __init__(self, cache_dict):
        self._cache_dict = cache_dict

    def write(self, name, val):
        logger.debug("Caching configuration item '%s' = %s" % (name, val))
        self._cache_dict[name] = val


default_configuration = collections.OrderedDict({
        'site': collections.OrderedDict({
            'title': "Untitled PieCrust website",
            'root': '/',
            'default_format': DEFAULT_FORMAT,
            'default_template_engine': DEFAULT_TEMPLATE_ENGINE,
            'enable_gzip': True,
            'pretty_urls': False,
            'trailing_slash': False,
            'date_format': DEFAULT_DATE_FORMAT,
            'auto_formats': collections.OrderedDict([
                ('html', ''),
                ('md', 'markdown'),
                ('textile', 'textile')]),
            'default_auto_format': 'md',
            'default_pagination_source': None,
            'pagination_suffix': '/%num%',
            'slugify_mode': 'encode',
            'themes_sources': [DEFAULT_THEME_SOURCE],
            'cache_time': 28800,
            'enable_debug_info': True,
            'show_debug_info': False,
            'use_default_content': True,
            'theme_site': False
            }),
        'baker': collections.OrderedDict({
            'no_bake_setting': 'draft',
            'workers': None,
            'batch_size': None
            })
        })


default_content_model_base = collections.OrderedDict({
        'site': collections.OrderedDict({
            'posts_fs': DEFAULT_POSTS_FS,
            'date_format': DEFAULT_DATE_FORMAT,
            'default_page_layout': 'default',
            'default_post_layout': 'post',
            'post_url': '%year%/%month%/%day%/%slug%',
            'tag_url': 'tag/%tag%',
            'category_url': '%category%',
            'posts_per_page': 5
            })
        })


def get_default_content_model(values):
    default_layout = values['site']['default_page_layout']
    return collections.OrderedDict({
            'site': collections.OrderedDict({
                'sources': collections.OrderedDict({
                    'pages': {
                        'type': 'default',
                        'ignore_missing_dir': True,
                        'data_endpoint': 'site.pages',
                        'default_layout': default_layout,
                        'item_name': 'page'
                        }
                    }),
                'routes': [
                    {
                        'url': '/%path:slug%',
                        'source': 'pages',
                        'func': 'pcurl(slug)'
                        }
                    ],
                'taxonomies': collections.OrderedDict({
                    'tags': {
                        'multiple': True,
                        'term': 'tag'
                        },
                    'categories': {
                        'term': 'category'
                        }
                    })
                })
            })


def get_default_content_model_for_blog(
        blog_name, is_only_blog, values, theme_site=False):
    posts_fs = values['site']['posts_fs']
    blog_cfg = values.get(blog_name, {})

    if is_only_blog:
        url_prefix = ''
        tax_page_prefix = ''
        fs_endpoint = 'posts'
        data_endpoint = 'blog'
        item_name = 'post'
    else:
        url_prefix = blog_name + '/'
        tax_page_prefix = blog_name + '/'
        fs_endpoint = 'posts/%s' % blog_name
        data_endpoint = blog_name
        item_name = '%s-post' % blog_name

    items_per_page = blog_cfg.get(
            'posts_per_page', values['site']['posts_per_page'])
    date_format = blog_cfg.get(
            'date_format', values['site']['date_format'])
    default_layout = blog_cfg.get(
            'default_layout', values['site']['default_post_layout'])

    post_url = '/' + blog_cfg.get(
            'post_url',
            url_prefix + values['site']['post_url']).lstrip('/')
    tag_url = '/' + blog_cfg.get(
            'tag_url',
            url_prefix + values['site']['tag_url']).lstrip('/')
    category_url = '/' + blog_cfg.get(
            'category_url',
            url_prefix + values['site']['category_url']).lstrip('/')

    tags_taxonomy = 'pages:%s_tag.%%ext%%' % tax_page_prefix
    category_taxonomy = 'pages:%s_category.%%ext%%' % tax_page_prefix
    if not theme_site:
        tags_taxonomy += ';theme_pages:_tag.%ext%'
        category_taxonomy += ';theme_pages:_category.%ext%'

    return collections.OrderedDict({
            'site': collections.OrderedDict({
                'sources': collections.OrderedDict({
                    blog_name: collections.OrderedDict({
                        'type': 'posts/%s' % posts_fs,
                        'fs_endpoint': fs_endpoint,
                        'data_endpoint': data_endpoint,
                        'item_name': item_name,
                        'ignore_missing_dir': True,
                        'data_type': 'blog',
                        'items_per_page': items_per_page,
                        'date_format': date_format,
                        'default_layout': default_layout,
                        'taxonomy_pages': collections.OrderedDict({
                            'tags': tags_taxonomy,
                            'categories': category_taxonomy
                            })
                        })
                    }),
                'routes': [
                    {
                        'url': post_url,
                        'source': blog_name,
                        'func': 'pcposturl(year,month,day,slug)'
                        },
                    {
                        'url': tag_url,
                        'source': blog_name,
                        'taxonomy': 'tags',
                        'func': 'pctagurl(tag)'
                        },
                    {
                        'url': category_url,
                        'source': blog_name,
                        'taxonomy': 'categories',
                        'func': 'pccaturl(category)'
                        }
                    ]
                })
            })


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

# Make sure the site root starts and ends with a slash.
def _validate_site_root(v, values, cache):
    if not v.startswith('/'):
        raise ConfigurationError("The `site/root` setting must start "
                                 "with a slash.")
    root_url = urllib.parse.quote(v.rstrip('/') + '/')
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

    theme_site = values['site']['theme_site']
    if not theme_site:
        # Add the theme page source if no sources were defined in the theme
        # configuration itself.
        has_any_theme_source = False
        for sn, sc in v.items():
            if sc.get('realm') == REALM_THEME:
                has_any_theme_source = True
                break
        if not has_any_theme_source:
            v['theme_pages'] = {
                    'theme_source': True,
                    'fs_endpoint': 'pages',
                    'ignore_missing_dir': True,
                    'data_endpoint': 'site/pages',
                    'item_name': 'page',
                    'realm': REALM_THEME}
            values['site']['routes'].append({
                    'url': '/%path:slug%',
                    'source': 'theme_pages',
                    'func': 'pcurl(slug)'})

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
        sc.setdefault('data_endpoint', sn)
        sc.setdefault('data_type', 'iterator')
        sc.setdefault('item_name', sn)
        sc.setdefault('items_per_page', 5)
        sc.setdefault('date_format', DEFAULT_DATE_FORMAT)
        sc.setdefault('realm', REALM_USER)

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
        if rc.get('source') is None:
            raise ConfigurationError("Routes must specify a source.")
        if rc['source'] not in list(values['site']['sources'].keys()):
            raise ConfigurationError("Route is referencing unknown "
                                     "source: %s" % rc['source'])
        rc.setdefault('taxonomy', None)
        rc.setdefault('page_suffix', '/%num%')

    return v


def _validate_site_taxonomies(v, values, cache):
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

