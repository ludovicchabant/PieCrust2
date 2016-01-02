from piecrust.appconfig import PieCrustConfiguration


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
    values = {'site': {
        'sources': {'notes': {}},
        'routes': [{'url': '/notes/%path:slug%', 'source': 'notes'}]
        }}
    config = PieCrustConfiguration(values=values)
    # The order of routes is important. Sources, not so much.
    assert list(map(lambda v: v['source'], config.get('site/routes'))) == [
            'notes', 'pages', 'posts', 'posts', 'posts', 'theme_pages']
    assert list(config.get('site/sources').keys()) == [
            'posts', 'pages', 'notes', 'theme_pages']

