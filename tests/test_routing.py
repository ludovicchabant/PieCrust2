import pytest
from piecrust.routing import Route
from .mockutil import get_mock_app


@pytest.mark.parametrize(
        'config, metadata, expected',
        [
            ({'url': '/%foo%'},
                {'foo': 'bar'}, True),
            ({'url': '/%foo%'},
                {'zoo': 'zar', 'foo': 'bar'}, True),
            ({'url': '/%foo%'},
                {'zoo': 'zar'}, False),
            ({'url': '/%foo%/%zoo%'},
                {'zoo': 'zar'}, False)
            ])
def test_matches_metadata(config, metadata, expected):
    app = get_mock_app()
    app.config.set('site/root', '/')
    config.setdefault('source', 'blah')
    route = Route(app, config)
    m = route.matchesMetadata(metadata)
    assert m == expected


@pytest.mark.parametrize(
        'site_root, route_pattern, expected_required_metadata',
        [
            ('/', '/%foo%', set(['foo'])),
            ('/', '/%path:foo%', set(['foo'])),
            ('/', '/%foo%/%bar%', set(['foo', 'bar'])),
            ('/', '/%foo%/%path:bar%', set(['foo', 'bar'])),
            ('/something', '/%foo%', set(['foo'])),
            ('/something', '/%path:foo%', set(['foo'])),
            ('/something', '/%foo%/%bar%', set(['foo', 'bar'])),
            ('/something', '/%foo%/%path:bar%', set(['foo', 'bar']))
            ])
def test_required_metadata(site_root, route_pattern,
                           expected_required_metadata):
    app = get_mock_app()
    app.config.set('site/root', site_root.rstrip('/') + '/')
    config = {'url': route_pattern, 'source': 'blah'}
    route = Route(app, config)
    assert route.required_route_metadata == expected_required_metadata


@pytest.mark.parametrize(
        'site_root, config, uri, expected_match',
        [
            ('/', {'url': '/%foo%'},
                'something',
                {'foo': 'something'}),
            ('/', {'url': '/%foo%'},
                'something/other',
                None),
            ('/', {'url': '/%path:foo%'},
                'something/other',
                {'foo': 'something/other'}),
            ('/', {'url': '/%path:foo%'},
                '',
                {'foo': ''}),
            ('/', {'url': '/prefix/%path:foo%'},
                'prefix/something/other',
                {'foo': 'something/other'}),
            ('/', {'url': '/prefix/%path:foo%'},
                'prefix/',
                {'foo': ''}),
            ('/', {'url': '/prefix/%path:foo%'},
                'prefix',
                {}),

            ('/blah', {'url': '/%foo%'},
                'something',
                {'foo': 'something'}),
            ('/blah', {'url': '/%foo%'},
                'something/other',
                None),
            ('/blah', {'url': '/%path:foo%'},
                'something/other',
                {'foo': 'something/other'}),
            ('/blah', {'url': '/%path:foo%'},
                '',
                {'foo': ''}),
            ('/blah', {'url': '/prefix/%path:foo%'},
                'prefix/something/other',
                {'foo': 'something/other'}),
            ('/blah', {'url': '/prefix/%path:foo%'},
                'prefix/',
                {'foo': ''}),
            ('/blah', {'url': '/prefix/%path:foo%'},
                'prefix',
                {}),
            ])
def test_match_uri(site_root, config, uri, expected_match):
    site_root = site_root.rstrip('/') + '/'
    app = get_mock_app()
    app.config.set('site/root', site_root)
    config.setdefault('source', 'blah')
    route = Route(app, config)
    assert route.uri_pattern == config['url'].lstrip('/')
    m = route.matchUri(site_root + uri)
    assert m == expected_match


@pytest.mark.parametrize(
        'site_root',
        [
            ('/'), ('/whatever')
            ])
def test_match_uri_requires_absolute_uri(site_root):
    with pytest.raises(Exception):
        app = get_mock_app()
        app.config.set('site/root', site_root.rstrip('/') + '/')
        config = {'url': '/%path:slug%', 'source': 'blah'}
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
    app = get_mock_app()
    app.config.set('site/root', '/blah/')
    app.config.set('site/pretty_urls', pretty)
    app.config.set('site/trailing_slash', False)
    app.config.set('__cache/pagination_suffix_format', '/%(num)d')

    config = {'url': '/%path:slug%', 'source': 'blah'}
    route = Route(app, config)
    uri = route.getUri({'slug': slug}, sub_num=page_num)
    assert uri == ('/blah/' + expected)

