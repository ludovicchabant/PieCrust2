from piecrust.rendering import PageRenderingContext, render_page
from .mockutil import mock_fs, mock_fs_scope


def test_blog_provider():
    fs = (mock_fs()
          .withPage('posts/2015-03-01_one.md',
                    {'title': 'One', 'category': 'Foo'})
          .withPage('posts/2015-03-02_two.md',
                    {'title': 'Two', 'category': 'Foo'})
          .withPage('posts/2015-03-03_three.md',
                    {'title': 'Three', 'category': 'Bar'})
          .withPage('pages/categories.md',
                    {'format': 'none', 'layout': 'none'},
                    "{%for c in blog.categories%}\n"
                    "{{c.name}} ({{c.post_count}})\n"
                    "{%endfor%}\n"))
    with mock_fs_scope(fs):
        app = fs.getApp()
        page = app.getSource('pages').getPage({'slug': 'categories'})
        ctx = PageRenderingContext(page, '/categories')
        rp = render_page(ctx)
        expected = "\nBar (1)\n\nFoo (2)\n"
        assert rp.content == expected

