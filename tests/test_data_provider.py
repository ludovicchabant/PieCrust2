from .mockutil import mock_fs, mock_fs_scope
from .rdrutil import render_simple_page


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
        page = app.getSimplePage('tags.md')
        actual = render_simple_page(page)
        expected = "\nBar (1)\n\nFoo (2)\n"
        assert actual == expected

