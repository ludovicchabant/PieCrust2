import mock
import pytest
from piecrust.uriutil import UriInfo, parse_uri, get_first_sub_uri


@pytest.mark.parametrize('routes, uri, expected', [
        ({}, '/foo', None),
        (
            {'/articles/%slug%': {'source': 'dummy'}},
            '/articles/foo',
            UriInfo('', 'dummy', {'slug': 'foo'})),
        (
            {'/foo/%bar%': {'source': 'foo'},
                '/other/%one%-%two%': {'source': 'other'}},
            '/other/some-thing',
            UriInfo('', 'other', {'one': 'some', 'two': 'thing'}))
    ])
def test_parse_uri(routes, uri, expected):
    if expected is not None:
        expected.uri = uri
    for pattern, args in routes.items():
        if 'taxonomy' not in args:
            args['taxonomy'] = None

    actual = parse_uri(routes, uri)
    assert actual == expected


@pytest.mark.parametrize('uri, expected, pretty_urls', [
    ('foo/bar', 'foo/bar', True),
    ('foo/bar/2', 'foo/bar', True),
    ('foo/bar.ext', 'foo/bar.ext', True),
    ('foo/bar.ext/2', 'foo/bar.ext', True),
    ('foo/bar.html', 'foo/bar.html', False),
    ('foo/bar/2.html', 'foo/bar.html', False),
    ('foo/bar.ext', 'foo/bar.ext', False),
    ('foo/bar/2.ext', 'foo/bar.ext', False)
    ])
def test_get_first_sub_uri(uri, expected, pretty_urls):
    app = mock.MagicMock()
    app.config = {
            'site/pretty_urls': pretty_urls,
            '__cache/pagination_suffix_re': '/(\\d+)$'}
    actual = get_first_sub_uri(app, uri)
    assert actual == expected

