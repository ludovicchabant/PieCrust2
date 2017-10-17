import re
import pytest
import mock
from piecrust.serving.util import find_routes
from piecrust.sources.base import REALM_USER, REALM_THEME


@pytest.mark.parametrize(
    'uri, route_specs, expected',
    [
        ('/',
         [{'src': 'pages', 'pat': '(?P<path>.*)'}],
         [('pages', {'path': '/'})]),
        ('/',
         [{'src': 'pages', 'pat': '(?P<path>.*)'},
          {'src': 'theme', 'pat': '(?P<path>.*)', 'realm': REALM_THEME}],
         [('pages', {'path': '/'}), ('theme', {'path': '/'})])
    ])
def test_find_routes(uri, route_specs, expected):
    routes = []
    for rs in route_specs:
        m = mock.Mock()
        m.source_name = rs['src']
        m.source_realm = rs.setdefault('realm', REALM_USER)
        m.uri_re = re.compile(rs['pat'])
        m.matchUri = lambda u: m.uri_re.match(u).groupdict()
        routes.append(m)
    matching = find_routes(routes, uri)

    assert len(matching) == len(expected)
    for i in range(len(matching)):
        route, metadata, is_sub_page = matching[i]
        exp_source, exp_md = expected[i]
        assert route.source_name == exp_source
        assert metadata == exp_md
