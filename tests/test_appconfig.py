from piecrust.appconfig import PieCrustConfiguration
from .mockutil import mock_fs, mock_fs_scope


def test_config_default():
    values = {}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert len(config.get('site/sources')) == 2  # pages, posts


def test_config_default2():
    config = PieCrustConfiguration()
    assert config.get('site/root') == '/'
    assert len(config.get('site/sources')) == 2  # pages, posts


def test_config_site_override_title():
    values = {'site': {'title': "Whatever"}}
    config = PieCrustConfiguration(values=values)
    assert config.get('site/root') == '/'
    assert config.get('site/title') == 'Whatever'


def test_config_site_add_source():
    values = {'site': {
        'sources': {'notes': {}},
        'routes': [{'url': '/notes/%path:slug%', 'source': 'notes'}]
        }}
    config = PieCrustConfiguration(values=values)
    # The order of routes is important. Sources, not so much.
    # `posts` shows up 3 times in routes (posts, tags, categories)
    assert list(map(lambda v: v['source'], config.get('site/routes'))) == [
            'notes', 'posts', 'posts', 'posts', 'pages']
    assert sorted(config.get('site/sources').keys()) == sorted([
            'pages', 'posts', 'notes'])


def test_config_site_add_source_with_theme():
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
        assert sorted(app.config.get('site/sources').keys()) == sorted([
            'pages', 'posts', 'notes', 'theme_pages'])

