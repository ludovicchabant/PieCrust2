import mock
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
    app = mock.Mock()
    app.config = {'site/root': '/'}
    config.setdefault('source', 'blah')
    route = Route(app, config)
    m = route.matchesMetadata(metadata)
    assert m == expected


@pytest.mark.parametrize(
        'config, uri, expected_match',
        [
            ({'url': '/%foo%'},
                'something',
                {'foo': 'something'}),
            ({'url': '/%foo%'},
                'something/other',
                None),
            ({'url': '/%path:foo%'},
                'something/other',
                {'foo': 'something/other'}),
            ({'url': '/%path:foo%'},
                '',
                {'foo': ''}),
            ({'url': '/prefix/%path:foo%'},
                'prefix/something/other',
                {'foo': 'something/other'}),
            ({'url': '/prefix/%path:foo%'},
                'prefix/',
                {'foo': ''}),
            ({'url': '/prefix/%path:foo%'},
                'prefix',
                {}),
            ])
def test_match_uri(config, uri, expected_match):
    app = mock.Mock()
    app.config = {'site/root': '/'}
    config.setdefault('source', 'blah')
    route = Route(app, config)
    assert route.uri_pattern == config['url'].lstrip('/')
    m = route.matchUri(uri)
    assert m == expected_match


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
    app.config.set('site/root', '/blah')
    app.config.set('site/pretty_urls', pretty)
    app.config.set('site/trailing_slash', False)
    app.config.set('__cache/pagination_suffix_format', '/%(num)d')

    config = {'url': '/%path:slug%', 'source': 'blah'}
    route = Route(app, config)
    uri = route.getUri({'slug': slug}, sub_num=page_num)
    assert uri == ('/blah/' + expected)

