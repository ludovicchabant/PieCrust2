import urllib.parse
import mock
import pytest
from piecrust.routing import Route, RouteParameter
from piecrust.sources.base import ContentSource
from .mockutil import get_mock_app


def _getMockSource(name, params):
    route_params = []
    for p in params:
        if isinstance(p, tuple):
            if p[1] == 'path':
                t = RouteParameter.TYPE_PATH
            elif p[1] == 'int2':
                t = RouteParameter.TYPE_INT2
            elif p[2] == 'int4':
                t = RouteParameter.TYPE_INT4
            route_params.append(RouteParameter(p[0], t))
        else:
            route_params.append(RouteParameter(p, RouteParameter.TYPE_STRING))

    src = mock.MagicMock(spec=ContentSource)
    src.name = name
    src.getSupportedRouteParameters = lambda: route_params
    return src


@pytest.mark.parametrize(
    'config, params, uri_params, expected',
    [
        ({'url': '/%foo%'}, ['foo'], {'foo': 'bar'}, True),
        ({'url': '/%foo%'}, ['foo'], {'zoo': 'zar', 'foo': 'bar'}, True),
        ({'url': '/%foo%'}, ['foo'], {'zoo': 'zar'}, False),
        ({'url': '/%foo%/%zoo%'}, ['foo', 'zoo'], {'zoo': 'zar'}, False)
    ])
def test_matches_parameters(config, params, uri_params, expected):
    app = get_mock_app()
    app.config.set('site/root', '/')
    app.sources = [_getMockSource('blah', params)]

    config.setdefault('source', 'blah')
    route = Route(app, config)
    m = route.matchesParameters(uri_params)
    assert m == expected


@pytest.mark.parametrize(
    'site_root, route_pattern, params, expected_func_parameters',
    [
        ('/', '/%foo%', ['foo'], ['foo']),
        ('/', '/%foo%', [('foo', 'path')], ['foo']),
        ('/', '/%foo%/%bar%', ['foo', 'bar'], ['foo', 'bar']),
        ('/', '/%foo%/%bar%', ['foo', ('bar', 'path')], ['foo', 'bar']),
        ('/something', '/%foo%', ['foo'], ['foo']),
        ('/something', '/%foo%', [('foo', 'path')], ['foo']),
        ('/something', '/%foo%/%bar%', ['foo', 'bar'], ['foo', 'bar']),
        ('/something', '/%foo%/%bar%', ['foo', ('bar', 'path')],
         ['foo', 'bar']),
        ('/~johndoe', '/%foo%', ['foo'], ['foo']),
        ('/~johndoe', '/%foo%', [('foo', 'path')], ['foo']),
        ('/~johndoe', '/%foo%/%bar%', ['foo', 'bar'], ['foo', 'bar']),
        ('/~johndoe', '/%foo%/%bar%', ['foo', ('bar', 'path')], ['foo', 'bar'])
    ])
def test_required_metadata(site_root, route_pattern, params,
                           expected_func_parameters):
    app = get_mock_app()
    app.config.set('site/root', site_root.rstrip('/') + '/')
    app.sources = [_getMockSource('blah', params)]

    config = {'url': route_pattern, 'source': 'blah'}
    route = Route(app, config)
    assert route.uri_params == expected_func_parameters


@pytest.mark.parametrize(
    'site_root, config, params, uri, expected_match',
    [
        ('/', {'url': '/%foo%'},
         ['foo'],
         'something',
         {'foo': 'something'}),
        ('/', {'url': '/%foo%'},
         ['foo'],
         'something/other',
         None),
        ('/', {'url': '/%foo%'},
         [('foo', 'path')],
         'something/other',
         {'foo': 'something/other'}),
        ('/', {'url': '/%foo%'},
         [('foo', 'path')],
         '',
         {'foo': ''}),
        ('/', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix/something/other',
         {'foo': 'something/other'}),
        ('/', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix/',
         {'foo': ''}),
        ('/', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix',
         {'foo': ''}),

        ('/blah', {'url': '/%foo%'},
         ['foo'],
         'something',
         {'foo': 'something'}),
        ('/blah', {'url': '/%foo%'},
         ['foo'],
         'something/other',
         None),
        ('/blah', {'url': '/%foo%'},
         [('foo', 'path')],
         'something/other',
         {'foo': 'something/other'}),
        ('/blah', {'url': '/%foo%'},
         [('foo', 'path')],
         '',
         {'foo': ''}),
        ('/blah', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix/something/other',
         {'foo': 'something/other'}),
        ('/blah', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix/',
         {'foo': ''}),
        ('/blah', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix',
         {'foo': ''}),

        ('/~johndoe', {'url': '/%foo%'},
         ['foo'],
         'something',
         {'foo': 'something'}),
        ('/~johndoe', {'url': '/%foo%'},
         ['foo'],
         'something/other',
         None),
        ('/~johndoe', {'url': '/%foo%'},
         [('foo', 'path')],
         'something/other',
         {'foo': 'something/other'}),
        ('/~johndoe', {'url': '/%foo%'},
         [('foo', 'path')],
         '',
         {'foo': ''}),
        ('/~johndoe', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix/something/other',
         {'foo': 'something/other'}),
        ('/~johndoe', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix/',
         {'foo': ''}),
        ('/~johndoe', {'url': '/prefix/%foo%'},
         [('foo', 'path')],
         'prefix',
         {'foo': ''}),
    ])
def test_match_uri(site_root, config, params, uri, expected_match):
    site_root = site_root.rstrip('/') + '/'
    app = get_mock_app()
    app.config.set('site/root', urllib.parse.quote(site_root))
    app.sources = [_getMockSource('blah', params)]

    config.setdefault('source', 'blah')
    route = Route(app, config)
    assert route.uri_pattern == config['url'].lstrip('/')
    m = route.matchUri(urllib.parse.quote(site_root) + uri)
    assert m == expected_match


@pytest.mark.parametrize(
    'site_root',
    [
        ('/'),
        ('/whatever'),
        ('/~johndoe')
    ])
def test_match_uri_requires_absolute_uri(site_root):
    with pytest.raises(Exception):
        app = get_mock_app()
        app.config.set('site/root', site_root.rstrip('/') + '/')
        app.sources = [_getMockSource('blah', [('slug', 'path')])]

        config = {'url': '/%slug%', 'source': 'blah'}
        route = Route(app, config)
        route.matchUri('notabsuri')


@pytest.mark.parametrize(
    'slug, page_num, pretty, expected',
    [
        # Pretty URLs
        ('', 1, True, ''),
        ('', 2, True, '2'),
        ('foo', 1, True, 'foo'),
        ('foo', 2, True, 'foo/2'),
        ('foo/bar', 1, True, 'foo/bar'),
        ('foo/bar', 2, True, 'foo/bar/2'),
        ('foo.ext', 1, True, 'foo.ext'),
        ('foo.ext', 2, True, 'foo.ext/2'),
        ('foo/bar.ext', 1, True, 'foo/bar.ext'),
        ('foo/bar.ext', 2, True, 'foo/bar.ext/2'),
        ('foo.bar.ext', 1, True, 'foo.bar.ext'),
        ('foo.bar.ext', 2, True, 'foo.bar.ext/2'),
        # Ugly URLs
        ('', 1, False, ''),
        ('', 2, False, '2.html'),
        ('foo', 1, False, 'foo.html'),
        ('foo', 2, False, 'foo/2.html'),
        ('foo/bar', 1, False, 'foo/bar.html'),
        ('foo/bar', 2, False, 'foo/bar/2.html'),
        ('foo.ext', 1, False, 'foo.ext'),
        ('foo.ext', 2, False, 'foo/2.ext'),
        ('foo/bar.ext', 1, False, 'foo/bar.ext'),
        ('foo/bar.ext', 2, False, 'foo/bar/2.ext'),
        ('foo.bar.ext', 1, False, 'foo.bar.ext'),
        ('foo.bar.ext', 2, False, 'foo.bar/2.ext')
    ])
def test_get_uri(slug, page_num, pretty, expected):
    for root in ['/', '/blah/', '/~johndoe/']:
        app = get_mock_app()
        app.config.set('site/root', urllib.parse.quote(root))
        app.config.set('site/pretty_urls', pretty)
        app.config.set('site/trailing_slash', False)
        app.config.set('__cache/pagination_suffix_format', '/%(num)d')
        app.sources = [_getMockSource('blah', [('slug', 'path')])]

        config = {'url': '/%slug%', 'source': 'blah'}
        route = Route(app, config)
        uri = route.getUri({'slug': slug}, sub_num=page_num)
        assert uri == (urllib.parse.quote(root) + expected)

