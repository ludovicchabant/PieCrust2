import yaml
from piecrust.appconfig import PieCrustConfiguration
from .mockutil import mock_fs, mock_fs_scope


def test_config_default():
    values = {}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert len(config.get('site/sources')) == 3  # pages, posts, theme_pages


def test_config_default2():
    config = PieCrustConfiguration()
    assert config.get('site/root') == '/'
    assert len(config.get('site/sources')) == 3  # pages, posts, theme_pages


def test_config_site_override_title():
    values = {'site': {'title': "Whatever"}}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert config.get('site/title') == 'Whatever'


def test_config_site_add_source():
    config = {'site': {
        'sources': {'notes': {}},
        'routes': [{'url': '/notes/%path:slug%', 'source': 'notes'}]
        }}
    fs = mock_fs().withConfig(config)
    with mock_fs_scope(fs):
        app = fs.getApp()
        # The order of routes is important. Sources, not so much.
        # `posts` shows up 3 times in routes (posts, tags, categories)
        assert (list(
            map(
                lambda v: v['source'],
                app.config.get('site/routes'))) ==
            ['notes', 'posts', 'posts', 'posts', 'pages', 'theme_pages'])
        assert list(app.config.get('site/sources').keys()) == [
            'theme_pages', 'pages', 'posts', 'notes']


def test_config_site_add_source_in_both_site_and_theme():
    theme_config = {'site': {
        'sources': {'theme_notes': {}},
        'routes': [{'url': '/theme_notes/%path:slug%', 'source': 'theme_notes'}]
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
                lambda v: v['source'],
                app.config.get('site/routes'))) ==
            ['notes', 'posts', 'posts', 'posts', 'pages', 'theme_notes', 'theme_pages'])
        assert list(app.config.get('site/sources').keys()) == [
            'theme_pages', 'theme_notes', 'pages', 'posts', 'notes']

