import re
import pytest
import mock
from piecrust.data.filters import (
        PaginationFilter, HasFilterClause, IsFilterClause,
        page_value_accessor)
from piecrust.rendering import QualifiedPage, PageRenderingContext, render_page
from piecrust.serving import find_routes
from piecrust.sources.base import REALM_USER, REALM_THEME
from .mockutil import mock_fs, mock_fs_scope


@pytest.mark.parametrize('uri, route_specs, expected',
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
        route, metadata = matching[i]
        exp_source, exp_md = expected[i]
        assert route.source_name == exp_source
        assert metadata == exp_md


@pytest.mark.parametrize(
        'tag, expected_indices',
        [
            ('foo', [1, 2, 4, 5, 6]),
            ('bar', [2, 3, 4, 6, 8]),
            ('whatever', [5, 8]),
            ('unique', [7]),
            ('missing', None)
        ])
def test_serve_tag_page(tag, expected_indices):
    tags = [
            ['foo'],
            ['foo', 'bar'],
            ['bar'],
            ['bar', 'foo'],
            ['foo', 'whatever'],
            ['foo', 'bar'],
            ['unique'],
            ['whatever', 'bar']]

    def config_factory(i):
        c = {'title': 'Post %d' % (i + 1)}
        c['tags'] = list(tags[i])
        return c

    fs = (mock_fs()
          .withPages(8, 'posts/2015-03-{idx1:02}_post{idx1:02}.md',
                     config_factory)
          .withPage('pages/_tag.md', {'layout': 'none', 'format': 'none'},
                    "Pages in {{tag}}\n"
                    "{%for p in pagination.posts -%}\n"
                    "{{p.title}}\n"
                    "{%endfor%}"))
    with mock_fs_scope(fs):
        app = fs.getApp()
        page = app.getSource('pages').getPage({'slug': '_tag', 'tag': tag})
        route = app.getTaxonomyRoute('tags', 'posts')
        route_metadata = {'slug': '_tag', 'tag': tag}
        taxonomy = app.getTaxonomy('tags')

        qp = QualifiedPage(page, route, route_metadata)
        ctx = PageRenderingContext(qp)
        ctx.setTaxonomyFilter(taxonomy, tag)
        rp = render_page(ctx)

        expected = "Pages in %s\n" % tag
        if expected_indices:
            for i in reversed(expected_indices):
                expected += "Post %d\n" % i
        assert expected == rp.content


@pytest.mark.parametrize(
        'category, expected_indices',
        [
            ('foo', [1, 2, 4]),
            ('bar', [3, 6]),
            ('missing', None)
        ])
def test_serve_category_page(category, expected_indices):
    categories = [
            'foo', 'foo', 'bar', 'foo', None, 'bar']

    def config_factory(i):
        c = {'title': 'Post %d' % (i + 1)}
        if categories[i]:
            c['category'] = categories[i]
        return c

    fs = (mock_fs()
          .withPages(6, 'posts/2015-03-{idx1:02}_post{idx1:02}.md',
                     config_factory)
          .withPage('pages/_category.md', {'layout': 'none', 'format': 'none'},
                    "Pages in {{category}}\n"
                    "{%for p in pagination.posts -%}\n"
                    "{{p.title}}\n"
                    "{%endfor%}"))
    with mock_fs_scope(fs):
        app = fs.getApp()
        page = app.getSource('pages').getPage({'slug': '_category',
                                               'category': category})
        route = app.getTaxonomyRoute('categories', 'posts')
        route_metadata = {'slug': '_category', 'category': category}
        taxonomy = app.getTaxonomy('categories')

        qp = QualifiedPage(page, route, route_metadata)
        ctx = PageRenderingContext(qp)
        ctx.setTaxonomyFilter(taxonomy, category)
        rp = render_page(ctx)

        expected = "Pages in %s\n" % category
        if expected_indices:
            for i in reversed(expected_indices):
                expected += "Post %d\n" % i
        assert expected == rp.content

