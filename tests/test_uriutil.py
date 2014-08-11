import pytest
from piecrust.uriutil import UriInfo, parse_uri


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
    for pattern, args in routes.iteritems():
        if 'taxonomy' not in args:
            args['taxonomy'] = None

    actual = parse_uri(routes, uri)
    assert actual == expected

