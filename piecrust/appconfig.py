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
        try_get_dict_value, try_get_dict_values,
        set_dict_value, merge_dicts, visit_dict)
from piecrust.sources.base import REALM_USER, REALM_THEME


logger = logging.getLogger(__name__)


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
        self._custom_paths = []
        self._post_fixups = []
        self.theme_config = theme_config
        # Set the values after we set the rest, since our validation needs
        # our attributes.
        if values:
            self.setAll(values, validate=validate)

    def addPath(self, p):
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

    def setAll(self, values, validate=False):
        # Override base class implementation
        values = self._combineConfigs({}, values)
        if validate:
            values = self._validateAll(values)
        self._values = values

    def _ensureNotLoaded(self):
        if self._values is not None:
            raise Exception("The configurations has been loaded.")

    def _load(self):
        # Figure out where to load this configuration from.
        paths = [self._theme_path, self._path] + self._custom_paths
        paths = list(filter(lambda i: i is not None, paths))

        # Build the cache-key.
        path_times = [os.path.getmtime(p) for p in paths]
        cache_key_hash = hashlib.md5(
                ("version=%s&cache=%d" % (
                    APP_VERSION, CACHE_VERSION)).encode('utf8'))
        for p in paths:
            cache_key_hash.update(("&path=%s" % p).encode('utf8'))
        cache_key = cache_key_hash.hexdigest()

        # Check the cache for a valid version.
        if self._cache.isValid('config.json', path_times):
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
            # Theme config.
            theme_values = {}
            if self._theme_path:
                theme_values = self._loadFrom(self._theme_path)

            # Site config.
            site_values = {}
            if self._path:
                site_values = self._loadFrom(self._path)

            # Combine!
            logger.debug("Processing loaded configurations...")
            values = self._combineConfigs(theme_values, site_values)

            # Load additional paths.
            if self._custom_paths:
                logger.debug("Loading %d additional configuration paths." %
                             len(self._custom_paths))
                for p in self._custom_paths:
                    loaded = self._loadFrom(p)
                    if loaded:
                        merge_dicts(values, loaded)

            # Run final fixups
            if self._post_fixups:
                logger.debug("Applying %d configuration fixups." %
                             len(self._post_fixups))
                for f in self._post_fixups:
                    f(values)

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

    def _combineConfigs(self, theme_values, site_values):
        # Start with the default configuration.
        values = copy.deepcopy(default_configuration)

        if not self.theme_config:
            # If the theme config wants the default model, add it.
            theme_sitec = theme_values.setdefault(
                    'site', collections.OrderedDict())
            gen_default_theme_model = bool(theme_sitec.setdefault(
                    'use_default_theme_content', True))
            if gen_default_theme_model:
                self._generateDefaultThemeModel(values)

            # Now override with the actual theme config values.
            values = merge_dicts(values, theme_values)

        # Make all sources belong to the "theme" realm at this point.
        srcc = values['site'].get('sources')
        if srcc:
            for sn, sc in srcc.items():
                sc['realm'] = REALM_THEME

        # If the site config wants the default model, add it.
        site_sitec = site_values.setdefault(
                'site', collections.OrderedDict())
        gen_default_site_model = bool(site_sitec.setdefault(
                'use_default_content', True))
        if gen_default_site_model:
            self._generateDefaultSiteModel(values, site_values)

        # And override with the actual site config values.
        values = merge_dicts(values, site_values)

        # Set the theme site flag.
        if self.theme_config:
            values['site']['theme_site'] = True

        return values

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

    def _generateDefaultThemeModel(self, values):
        logger.debug("Generating default theme content model...")
        cc = copy.deepcopy(default_theme_content_model_base)
        merge_dicts(values, cc)

    def _generateDefaultSiteModel(self, values, user_overrides):
        logger.debug("Generating default content model...")
        cc = copy.deepcopy(default_content_model_base)
        merge_dicts(values, cc)

        dcm = get_default_content_model(values, user_overrides)
        merge_dicts(values, dcm)

        blogsc = try_get_dict_value(user_overrides, 'site/blogs')
        if blogsc is None:
            blogsc = ['posts']
            set_dict_value(user_overrides, 'site/blogs', blogsc)

        is_only_blog = (len(blogsc) == 1)
        for blog_name in blogsc:
            blog_cfg = get_default_content_model_for_blog(
                    blog_name, is_only_blog, values, user_overrides,
                    theme_site=self.theme_config)
            merge_dicts(values, blog_cfg)


class _ConfigCacheWriter(object):
    def __init__(self, cache_dict):
        self._cache_dict = cache_dict

    def write(self, name, val):
        logger.debug("Caching configuration item '%s' = %s" % (name, val))
        self._cache_dict[name] = val


default_theme_content_model_base = collections.OrderedDict({
        'site': collections.OrderedDict({
            'sources': collections.OrderedDict({
                'theme_pages': {
                    'type': 'default',
                    'ignore_missing_dir': True,
                    'fs_endpoint': 'pages',
                    'data_endpoint': 'site.pages',
                    'default_layout': 'default',
                    'item_name': 'page',
                    'realm': REALM_THEME
                    }
                }),
            'routes': [
                {
                    'url': '/%path:slug%',
                    'source': 'theme_pages',
                    'func': 'pcurl(slug)'
                    }
                ],
            'theme_tag_page': 'theme_pages:_tag.%ext%',
            'theme_category_page': 'theme_pages:_category.%ext%',
            'theme_month_page': 'theme_pages:_month.%ext%',
            'theme_year_page': 'theme_pages:_year.%ext%'
            })
        })


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
            'use_default_theme_content': True,
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
            'default_page_layout': 'default',
            'default_post_layout': 'post',
            'post_url': '/%int4:year%/%int2:month%/%int2:day%/%slug%',
            'year_url': '/archives/%int4:year%',
            'tag_url': '/tag/%path:tag%',
            'category_url': '/%category%',
            'posts_per_page': 5
            })
        })


def get_default_content_model(values, user_overrides):
    default_layout = try_get_dict_value(
            user_overrides, 'site/default_page_layout',
            values['site']['default_page_layout'])
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
                'taxonomies': collections.OrderedDict([
                    ('tags', {
                        'multiple': True,
                        'term': 'tag'
                        }),
                    ('categories', {
                        'term': 'category',
                        'func_name': 'pccaturl'
                        })
                    ])
                })
            })


def get_default_content_model_for_blog(
        blog_name, is_only_blog, values, user_overrides, theme_site=False):
    # Get the global (default) values for various things we're interested in.
    defs = {}
    names = ['posts_fs', 'posts_per_page', 'date_format',
             'default_post_layout', 'post_url', 'year_url']
    for n in names:
        defs[n] = try_get_dict_value(
                user_overrides, 'site/%s' % n,
                values['site'][n])

    # More stuff we need.
    if is_only_blog:
        url_prefix = ''
        page_prefix = ''
        fs_endpoint = 'posts'
        data_endpoint = 'blog'
        item_name = 'post'
        tpl_func_prefix = 'pc'

        if theme_site:
            # If this is a theme site, show posts from a `sample` directory
            # so it's clearer that those won't show up when the theme is
            # actually applied to a normal site.
            fs_endpoint = 'sample/posts'
    else:
        url_prefix = blog_name + '/'
        page_prefix = blog_name + '/'
        data_endpoint = blog_name
        fs_endpoint = 'posts/%s' % blog_name
        item_name = try_get_dict_value(user_overrides,
                                       '%s/item_name' % blog_name,
                                       '%spost' % blog_name)
        tpl_func_prefix = try_get_dict_value(user_overrides,
                                             '%s/func_prefix' % blog_name,
                                             'pc%s' % blog_name)

    # Figure out the settings values for this blog, specifically.
    # The value could be set on the blog config itself, globally, or left at
    # its default. We already handle the "globally vs. default" with the
    # `defs` map that we computed above.
    blog_cfg = user_overrides.get(blog_name, {})
    blog_values = {}
    for n in names:
        blog_values[n] = blog_cfg.get(n, defs[n])

    posts_fs = blog_values['posts_fs']
    posts_per_page = blog_values['posts_per_page']
    date_format = blog_values['date_format']
    default_layout = blog_values['default_post_layout']
    post_url = '/' + url_prefix + blog_values['post_url'].lstrip('/')
    year_url = '/' + url_prefix + blog_values['year_url'].lstrip('/')

    year_archive = 'pages:%s_year.%%ext%%' % page_prefix
    if not theme_site:
        theme_year_page = values['site'].get('theme_year_page')
        if theme_year_page:
            year_archive += ';' + theme_year_page

    cfg = collections.OrderedDict({
            'site': collections.OrderedDict({
                'sources': collections.OrderedDict({
                    blog_name: collections.OrderedDict({
                        'type': 'posts/%s' % posts_fs,
                        'fs_endpoint': fs_endpoint,
                        'data_endpoint': data_endpoint,
                        'item_name': item_name,
                        'ignore_missing_dir': True,
                        'data_type': 'blog',
                        'items_per_page': posts_per_page,
                        'date_format': date_format,
                        'default_layout': default_layout
                        })
                    }),
                'generators': collections.OrderedDict({
                    ('%s_archives' % blog_name): collections.OrderedDict({
                        'type': 'blog_archives',
                        'source': blog_name,
                        'page': year_archive
                        })
                    }),
                'routes': [
                    {
                        'url': post_url,
                        'source': blog_name,
                        'func': (
                            '%sposturl(int:year,int:month,int:day,slug)' %
                            tpl_func_prefix)
                        },
                    {
                        'url': year_url,
                        'generator': ('%s_archives' % blog_name),
                        'func': ('%syearurl(year)' % tpl_func_prefix)
                        }
                    ]
                })
            })

    # Add a generator and a route for each taxonomy.
    taxonomies_cfg = values.get('site', {}).get('taxonomies', {}).copy()
    taxonomies_cfg.update(
            user_overrides.get('site', {}).get('taxonomies', {}))
    for tax_name, tax_cfg in taxonomies_cfg.items():
        term = tax_cfg.get('term', tax_name)

        # Generator.
        page_ref = 'pages:%s_%s.%%ext%%' % (page_prefix, term)
        if not theme_site:
            theme_page_ref = values['site'].get('theme_%s_page' % term)
            if theme_page_ref:
                page_ref += ';' + theme_page_ref
        tax_gen_name = '%s_%s' % (blog_name, tax_name)
        tax_gen = collections.OrderedDict({
            'type': 'taxonomy',
            'source': blog_name,
            'taxonomy': tax_name,
            'page': page_ref
            })
        cfg['site']['generators'][tax_gen_name] = tax_gen

        # Route.
        tax_url_cfg_name = '%s_url' % term
        tax_url = try_get_dict_values(
                (blog_cfg, tax_url_cfg_name),
                (user_overrides, 'site/%s' % tax_url_cfg_name),
                (values, 'site/%s' % tax_url_cfg_name),
                default=('%s/%%%s%%' % (term, term)))
        tax_url = '/' + url_prefix + tax_url.lstrip('/')
        term_arg = term
        if tax_cfg.get('multiple') is True:
            term_arg = '+' + term
        tax_func_name = try_get_dict_values(
                (user_overrides, 'site/taxonomies/%s/func_name' % tax_name),
                (values, 'site/taxonomies/%s/func_name' % tax_name),
                default=('%s%surl' % (tpl_func_prefix, term)))
        tax_func = '%s(%s)' % (tax_func_name, term_arg)
        tax_route = collections.OrderedDict({
            'url': tax_url,
            'generator': tax_gen_name,
            'taxonomy': tax_name,
            'func': tax_func
            })
        cfg['site']['routes'].append(tax_route)

    return cfg


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
    generators = v.get('generators')
    if generators is None:
        v['generators'] = {}
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

        # Validate generators.
        for gn, gc in sc.get('generators', {}).items():
            if not isinstance(gc, dict):
                raise ConfigurationError(
                    "Generators for source '%s' should be defined in a "
                    "dictionary." % sn)
            gc['source'] = sn

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

        r_source = rc.get('source')
        r_generator = rc.get('generator')
        if r_source is None and r_generator is None:
            raise ConfigurationError("Routes must specify a source or "
                                     "generator.")
        if (r_source and
                r_source not in list(values['site']['sources'].keys())):
            raise ConfigurationError("Route is referencing unknown "
                                     "source: %s" % r_source)
        if (r_generator and
                r_generator not in list(values['site']['generators'].keys())):
            raise ConfigurationError("Route is referencing unknown "
                                     "generator: %s" % r_generator)

        rc.setdefault('generator', None)
        rc.setdefault('page_suffix', '/%num%')

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


def _validate_site_generators(v, values, cache):
    if not isinstance(v, dict):
        raise ConfigurationError(
                "The 'site/generators' setting must be a mapping.")
    for gn, gc in v.items():
        if 'type' not in gc:
            raise ConfigurationError(
                    "Generator '%s' doesn't specify a type." % gn)
    return v


def _validate_site_plugins(v, values, cache):
    if isinstance(v, str):
        v = v.split(',')
    elif not isinstance(v, list):
        raise ConfigurationError(
                "The 'site/plugins' setting must be an array, or a "
                "comma-separated list.")
    return v

