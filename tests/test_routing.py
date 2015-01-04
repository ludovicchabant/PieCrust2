import mock
import pytest
from piecrust.routing import Route


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

