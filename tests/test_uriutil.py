import mock
import pytest
from piecrust.uriutil import UriInfo, parse_uri, split_sub_uri


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
    ('/', ('/', 1), True),
    ('/2', ('/', 2), True),
    ('/foo/bar', ('/foo/bar', 1), True),
    ('/foo/bar/2', ('/foo/bar', 2), True),
    ('/foo/bar.ext', ('/foo/bar.ext', 1), True),
    ('/foo/bar.ext/2', ('/foo/bar.ext', 2), True),
    ('/', ('/', 1), False),
    ('/2.html', ('/', 2), False),
    ('/foo/bar.html', ('/foo/bar.html', 1), False),
    ('/foo/bar/2.html', ('/foo/bar.html', 2), False),
    ('/foo/bar.ext', ('/foo/bar.ext', 1), False),
    ('/foo/bar/2.ext', ('/foo/bar.ext', 2), False)
    ])
def test_split_sub_uri(uri, expected, pretty_urls):
    app = mock.MagicMock()
    app.config = {
            'site/root': '/',
            'site/pretty_urls': pretty_urls,
            '__cache/pagination_suffix_re': '/(?P<num>\\d+)$'}
    actual = split_sub_uri(app, uri)
    assert actual == (expected[0], expected[1])


@pytest.mark.parametrize('uri, expected, pretty_urls', [
    ('/', ('/', 1), True),
    ('/2/', ('/', 2), True),
    ('/foo/bar/', ('/foo/bar/', 1), True),
    ('/foo/bar/2/', ('/foo/bar/', 2), True),
    ('/foo/bar.ext/', ('/foo/bar.ext/', 1), True),
    ('/foo/bar.ext/2/', ('/foo/bar.ext/', 2), True),
    ])
def test_split_sub_uri_trailing_slash(uri, expected, pretty_urls):
    app = mock.MagicMock()
    app.config = {
            'site/root': '/',
            'site/pretty_urls': pretty_urls,
            'site/trailing_slash': True,
            '__cache/pagination_suffix_re': '/(?P<num>\\d+)$'}
    actual = split_sub_uri(app, uri)
    assert actual == (expected[0], expected[1])


@pytest.mark.parametrize('uri, expected, pretty_urls', [
    ('/', ('/', 1), True),
    ('/2', ('/', 2), True),
    ('/foo/bar', ('/foo/bar', 1), True),
    ('/foo/bar/2', ('/foo/bar', 2), True),
    ('/foo/bar.ext', ('/foo/bar.ext', 1), True),
    ('/foo/bar.ext/2', ('/foo/bar.ext', 2), True),
    ('/', ('/', 1), False),
    ('/2.html', ('/', 2), False),
    ('/foo/bar.html', ('/foo/bar.html', 1), False),
    ('/foo/bar/2.html', ('/foo/bar.html', 2), False),
    ('/foo/bar.ext', ('/foo/bar.ext', 1), False),
    ('/foo/bar/2.ext', ('/foo/bar.ext', 2), False)
    ])
def test_split_sub_uri_with_root(uri, expected, pretty_urls):
    app = mock.MagicMock()
    app.config = {
            'site/root': '/whatever/',
            'site/pretty_urls': pretty_urls,
            '__cache/pagination_suffix_re': '/(?P<num>\\d+)$'}
    actual = split_sub_uri(app, '/whatever' + uri)
    assert actual == ('/whatever' + expected[0], expected[1])

