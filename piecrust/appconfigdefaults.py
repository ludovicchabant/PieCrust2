import collections
from piecrust import (
    DEFAULT_FORMAT, DEFAULT_TEMPLATE_ENGINE, DEFAULT_POSTS_FS,
    DEFAULT_DATE_FORMAT, DEFAULT_THEME_SOURCE)
from piecrust.configuration import (
    get_dict_values, try_get_dict_values)


# Default configuration for all websites.
#
default_configuration = collections.OrderedDict({
    'site': collections.OrderedDict({
        'title': "Untitled PieCrust website",
        'root': '/',
        'default_format': DEFAULT_FORMAT,
        'default_template_engine': DEFAULT_TEMPLATE_ENGINE,
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
        'use_default_content': True,
        'use_default_theme_content': True,
        'theme_site': False
    }),
    'baker': collections.OrderedDict({
        'no_bake_setting': 'draft',
        'workers': None,
        'batch_size': None
    }),
    'server': collections.OrderedDict({
        'enable_gzip': True,
        'cache_time': 28800,
        'enable_debug_info': True,
        'show_debug_info': False
    }),
    'pipelines': collections.OrderedDict({
        'asset': collections.OrderedDict({
            'processors': ['all', '-uglifyjs', '-cleancss']
        })
    })
})


# Default content model for themes.
#
default_theme_content_model_base = collections.OrderedDict({
    'site': collections.OrderedDict({
        'sources': collections.OrderedDict({
            'theme_pages': {
                'fs_endpoint': 'pages',
                'ignore_missing_dir': True,
                'data_endpoint': 'site.pages',
                'item_name': 'page',
            },
            'theme_assets': {
                'fs_endpoint': 'assets',
                'ignore_missing_dir': True,
                'type': 'fs',
                'pipeline': 'asset'
            }
        }),
        'routes': [
            {
                'url': '/%slug%',
                'source': 'theme_pages',
                'func': 'pcurl'
            }
        ]
    })
})


# Additional theme configuration when previewing a theme by itself,
# so it can show some "sample/preview" content.
#
default_theme_preview_content_model = collections.OrderedDict({
    'site': collections.OrderedDict({
        'sources': collections.OrderedDict({
            'theme_preview_pages': {
                'fs_endpoint': 'preview/pages',
                'ignore_missing_dir': True,
                'data_endpoint': 'site.pages',
                'item_name': 'page',
            },
            'theme_preview_posts': {
                'fs_endpoint': 'preview/posts',
                'ignore_missing_dir': True,
                'data_endpoint': 'blog.posts',
                'item_name': 'post'
            }
        }),
        'routes': [
            {
                'url': '/posts/%year%/%month%/%slug%',
                'source': 'theme_preview_posts'
            },
            {
                'url': '/%slug%',
                'source': 'theme_preview_pages',
                'func': 'pcurl'
            }
        ]
    })
})


# Default content model for websites.
#
default_content_model_base = collections.OrderedDict({
    'site': collections.OrderedDict({
        'posts_fs': DEFAULT_POSTS_FS,
        'default_page_layout': 'default',
        'default_post_layout': 'post',
        'post_url': '/%year%/%month%/%day%/%slug%',
        'year_url': '/archives/%year%',
        'tag_url': '/tag/%tag%',
        'tag_feed_url': '/tag/%tag%.xml',
        'category_url': '/%category%',
        'category_feed_url': '/%category%.xml',
        'posts_per_page': 5,
        'sources': {
            'assets': {
                'fs_endpoint': 'assets',
                'ignore_missing_dir': True,
                'type': 'fs',
                'pipeline': 'asset'
            }
        }
    })
})


def get_default_content_model(site_values, values):
    default_layout = get_dict_values(
        (site_values, 'site/default_page_layout'),
        (values, 'site/default_page_layout'))
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
                    'url': '/%slug%',
                    'source': 'pages',
                    'func': 'pcurl'
                }
            ],
            'taxonomies': collections.OrderedDict([
                ('tags', {
                    'multiple': True,
                    'term': 'tag'
                }),
                ('categories', {
                    'term': 'category',
                    'func_term_name': 'cat'
                })
            ])
        })
    })


def get_default_content_model_for_blog(blog_name, is_only_blog,
                                       site_values, values,
                                       theme_site=False):
    # Get the global (default) values for various things we're interested in.
    defs = {}
    names = ['posts_fs', 'posts_per_page', 'date_format',
             'default_post_layout', 'post_url', 'year_url']
    for n in names:
        defs[n] = get_dict_values(
            (site_values, 'site/%s' % n),
            (values, 'site/%s' % n))

    # More stuff we need.
    if is_only_blog:
        url_prefix = ''
        page_prefix = ''
        fs_endpoint = 'posts'
        data_endpoint = 'blog'
        item_name = 'post'
        tpl_func_prefix = 'pc'
        year_archive_tpl = '_year.html'

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
        item_name = try_get_dict_values(
            (site_values, '%s/item_name' % blog_name),
            (values, '%s/item_name' % blog_name),
            default=('%spost' % blog_name))
        tpl_func_prefix = try_get_dict_values(
            (site_values, '%s/func_prefix' % blog_name),
            (values, '%s/func_prefix' % blog_name),
            default=('pc%s' % blog_name))
        year_archive_tpl = '%s_year.html,_year.html' % page_prefix

    # Figure out the settings values for this blog, specifically.
    # The value could be set on the blog config itself, globally, or left at
    # its default. We already handle the "globally vs. default" with the
    # `defs` map that we computed above.
    blog_cfg = values.get(blog_name, {})
    blog_values = {}
    for n in names:
        blog_values[n] = blog_cfg.get(n, defs[n])

    posts_fs = blog_values['posts_fs']
    posts_per_page = blog_values['posts_per_page']
    date_format = blog_values['date_format']
    default_layout = blog_values['default_post_layout']
    post_url = '/' + url_prefix + blog_values['post_url'].lstrip('/')
    year_url = '/' + url_prefix + blog_values['year_url'].lstrip('/')

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
                }),
                '%s_archives' % blog_name: collections.OrderedDict({
                    'type': 'blog_archives',
                    'source': blog_name,
                    'template': year_archive_tpl
                })
            }),
            'routes': [
                {
                    'url': post_url,
                    'source': blog_name,
                    'func': ('%sposturl' % tpl_func_prefix)
                },
                {
                    'url': year_url,
                    'source': ('%s_archives' % blog_name),
                    'func': ('%syearurl' % tpl_func_prefix)
                }
            ]
        })
    })

    # Add a source and a route for each taxonomy.
    taxonomies_cfg = try_get_dict_values(
        (site_values, 'site/taxonomies'),
        (values, 'site/taxonomies'),
        default={}).copy()
    for tax_name, tax_cfg in taxonomies_cfg.items():
        term = tax_cfg.get('term', tax_name)

        # Source.
        term_tpl = '%s_%s.html' % (page_prefix, term)
        tax_src_name = '%s_%s' % (blog_name, tax_name)
        tax_src = collections.OrderedDict({
            'type': 'taxonomy',
            'source': blog_name,
            'taxonomy': tax_name,
            'template': term_tpl
        })
        cfg['site']['sources'][tax_src_name] = tax_src

        # Route.
        tax_url_cfg_name = '%s_url' % term
        tax_url = try_get_dict_values(
            (blog_cfg, tax_url_cfg_name),
            (site_values, 'site/%s' % tax_url_cfg_name),
            (values, 'site/%s' % tax_url_cfg_name),
            default=('%s/%%%s%%' % (term, term)))
        tax_url = '/' + url_prefix + tax_url.lstrip('/')
        tax_func_term_name = try_get_dict_values(
            (site_values, 'site/taxonomies/%s/func_term_name' % tax_name),
            (values, 'site/taxonomies/%s/func_term_name' % tax_name),
            default=term)
        tax_func_name = '%s%surl' % (tpl_func_prefix, tax_func_term_name)
        tax_route = collections.OrderedDict({
            'url': tax_url,
            'pass': 2,
            'source': tax_src_name,
            'func': tax_func_name
        })
        cfg['site']['routes'].append(tax_route)

    return cfg

