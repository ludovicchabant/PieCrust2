from piecrust.rendering import QualifiedPage, PageRenderingContext, render_page
from .mockutil import mock_fs, mock_fs_scope


def test_blog_provider():
    fs = (mock_fs()
          .withConfig()
          .withPage('posts/2015-03-01_one.md',
                    {'title': 'One', 'tags': ['Foo']})
          .withPage('posts/2015-03-02_two.md',
                    {'title': 'Two', 'tags': ['Foo']})
          .withPage('posts/2015-03-03_three.md',
                    {'title': 'Three', 'tags': ['Bar']})
          .withPage('pages/tags.md',
                    {'format': 'none', 'layout': 'none'},
                    "{%for c in blog.tags%}\n"
                    "{{c.name}} ({{c.post_count}})\n"
                    "{%endfor%}\n"))
    with mock_fs_scope(fs):
        app = fs.getApp()
        page = app.getSource('pages').getPage({'slug': 'tags'})
        route = app.getSourceRoute('pages', None)
        route_metadata = {'slug': 'tags'}
        qp = QualifiedPage(page, route, route_metadata)
        ctx = PageRenderingContext(qp)
        rp = render_page(ctx)
        expected = "\nBar (1)\n\nFoo (2)\n"
        assert rp.content == expected

