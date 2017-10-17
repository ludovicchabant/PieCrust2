import pytest
from .mockutil import mock_fs, mock_fs_scope
from .rdrutil import render_simple_page


app_config = {
    'site': {
        'default_format': 'none',
        'default_template_engine': 'mustache'},
    'foo': 'bar'}
page_config = {'layout': 'none'}

open_patches = ['pystache.common']


@pytest.mark.parametrize(
    'contents, expected',
    [
        ("Raw text", "Raw text"),
        ("This is {{foo}}", "This is bar"),
        ("Info:\n{{#page}}\nMy URL: {{url}}\n{{/page}}\n",
         "Info:\nMy URL: /foo.html\n")
    ])
def test_simple(contents, expected):
    fs = (mock_fs()
          .withConfig(app_config)
          .withPage('pages/foo', config=page_config, contents=contents))
    with mock_fs_scope(fs, open_patches=open_patches):
        app = fs.getApp()
        page = fs.getSimplePage('foo.md')
        route = app.getSourceRoute('pages', None)
        route_metadata = {'slug': 'foo'}
        output = render_simple_page(page, route, route_metadata)
        assert output == expected


def test_layout():
    contents = "Blah\n"
    layout = "{{content}}\nFor site: {{foo}}\n"
    expected = "Blah\n\nFor site: bar\n"
    fs = (mock_fs()
          .withConfig(app_config)
          .withAsset('templates/blah.mustache', layout)
          .withPage('pages/foo', config={'layout': 'blah'},
                    contents=contents))
    with mock_fs_scope(fs, open_patches=open_patches):
        app = fs.getApp()
        page = fs.getSimplePage('foo.md')
        route = app.getSourceRoute('pages', None)
        route_metadata = {'slug': 'foo'}
        output = render_simple_page(page, route, route_metadata)
        # On Windows, pystache unexplicably adds `\r` to some newlines... wtf.
        output = output.replace('\r', '')
        assert output == expected


def test_partial():
    contents = "Info:\n{{#page}}\n{{> page_info}}\n{{/page}}\n"
    partial = "- URL: {{url}}\n- SLUG: {{slug}}\n"
    expected = "Info:\n- URL: /foo.html\n- SLUG: foo\n"
    fs = (mock_fs()
          .withConfig(app_config)
          .withAsset('templates/page_info.mustache', partial)
          .withPage('pages/foo', config=page_config, contents=contents))
    with mock_fs_scope(fs, open_patches=open_patches):
        app = fs.getApp()
        page = fs.getSimplePage('foo.md')
        route = app.getSourceRoute('pages', None)
        route_metadata = {'slug': 'foo'}
        output = render_simple_page(page, route, route_metadata)
        # On Windows, pystache unexplicably adds `\r` to some newlines... wtf.
        output = output.replace('\r', '')
        assert output == expected

