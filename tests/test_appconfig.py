import yaml
from piecrust.appconfig import PieCrustConfiguration
from .mockutil import mock_fs, mock_fs_scope


def test_config_default():
    values = {}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert len(config.get('site/sources').keys()) == \
        len(['theme_assets', 'assets', 'theme_pages', 'pages', 'posts',
             'tags', 'categories', 'archives'])


def test_config_site_override_title():
    values = {'site': {'title': "Whatever"}}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert config.get('site/title') == 'Whatever'


def test_config_override_default_model_settings():
    config = {'site': {
        'default_page_layout': 'foo',
        'default_post_layout': 'bar',
        'posts_per_page': 2}}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        assert app.config.get('site/default_page_layout') == 'foo'
        assert app.config.get('site/default_post_layout') == 'bar'
        assert app.config.get('site/sources/pages/default_layout') == 'foo'
        assert app.config.get('site/sources/pages/items_per_page') == 5
        assert app.config.get('site/sources/posts/default_layout') == 'bar'
        assert app.config.get('site/sources/posts/items_per_page') == 2
        assert app.config.get(
            'site/sources/theme_pages/default_layout') == 'default'
        assert app.config.get('site/sources/theme_pages/items_per_page') == 5


def test_config_site_add_source():
    config = {'site': {
        'sources': {'notes': {}},
        'routes': [{'url': '/notes/%path:slug%', 'source': 'notes'}]
    }}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        # The order of routes is important. Sources, not so much.
        assert (list(
            map(
                lambda v: v.get('generator') or v['source'],
                app.config.get('site/routes'))) ==
                [
                    'notes', 'posts', 'posts_archives', 'posts_tags',
                    'posts_categories', 'pages', 'theme_pages'])
        assert set(app.config.get('site/sources').keys()) == set([
            'theme_pages', 'theme_assets', 'pages', 'posts', 'assets',
            'posts_tags', 'posts_categories', 'posts_archives',
            'notes'])


def test_config_site_add_source_in_both_site_and_theme():
    theme_config = {'site': {
        'sources': {'theme_notes': {}},
        'routes': [{'url': '/theme_notes/%path:slug%',
                    'source': 'theme_notes'}]
    }}
    config = {'site': {
        'sources': {'notes': {}},
        'routes': [{'url': '/notes/%path:slug%', 'source': 'notes'}]
    }}
    fs = (mock_fs()
          .withConfig(config)
          .withFile('kitchen/theme/theme_config.yml', yaml.dump(theme_config)))
    with mock_fs_scope(fs):
        app = fs.getApp()
        # The order of routes is important. Sources, not so much.
        # `posts` shows up 3 times in routes (posts, tags, categories)
        assert (list(
            map(
                lambda v: v.get('generator') or v['source'],
                app.config.get('site/routes'))) ==
                [
                    'notes', 'posts', 'posts_archives', 'posts_tags',
                    'posts_categories', 'pages', 'theme_notes',
                    'theme_pages'])
        assert set(app.config.get('site/sources').keys()) == set([
            'theme_pages', 'theme_assets', 'theme_notes',
            'pages', 'posts', 'assets', 'posts_tags', 'posts_categories',
            'posts_archives', 'notes'])


def test_multiple_blogs():
    config = {'site': {'blogs': ['aaa', 'bbb']}}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        assert app.config.get('site/blogs') == ['aaa', 'bbb']
        assert (list(
            map(
                lambda v: v.get('generator') or v['source'],
                app.config.get('site/routes'))) ==
                [
                    'aaa', 'aaa_archives', 'aaa_tags', 'aaa_categories',
                    'bbb', 'bbb_archives', 'bbb_tags', 'bbb_categories',
                    'pages', 'theme_pages'])
        assert set(app.config.get('site/sources').keys()) == set([
            'aaa', 'aaa_tags', 'aaa_categories', 'aaa_archives',
            'bbb', 'bbb_tags', 'bbb_categories', 'bbb_archives',
            'pages', 'assets',
            'theme_pages', 'theme_assets'])


def test_custom_list_setting():
    config = {'blah': ['foo', 'bar']}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        assert app.config.get('blah') == ['foo', 'bar']


def test_custom_list_setting_in_site_section():
    config = {'site': {'blah': ['foo', 'bar']}}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        assert app.config.get('site/blah') == ['foo', 'bar']
