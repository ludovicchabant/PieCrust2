import pytest
from piecrust.data.linker import Linker
from .mockutil import mock_fs, mock_fs_scope, get_simple_content_item


@pytest.mark.parametrize(
    'fs_fac, page_path, expected',
    [
        (lambda: mock_fs().withPage('pages/foo'), 'foo',
         ['/foo']),
        ((lambda: mock_fs()
          .withPage('pages/foo')
          .withPage('pages/bar')),
         'foo',
         ['/bar', '/foo']),
        ((lambda: mock_fs()
          .withPage('pages/baz')
          .withPage('pages/something')
          .withPage('pages/something/else')
          .withPage('pages/foo')
          .withPage('pages/bar')),
         'foo',
         ['/bar', '/baz', '/foo', '/something']),
        ((lambda: mock_fs()
          .withPage('pages/something/else')
          .withPage('pages/foo')
          .withPage('pages/something/good')
          .withPage('pages/bar')),
         'something/else',
         ['/something/else', '/something/good'])
    ])
def test_linker_siblings(fs_fac, page_path, expected):
    fs = fs_fac()
    fs.withConfig()
    with mock_fs_scope(fs):
        app = fs.getApp()
        app.config.set('site/pretty_urls', True)
        src = app.getSource('pages')
        item = get_simple_content_item(app, page_path)
        linker = Linker(src, item)
        actual = list(linker.siblings)
        assert sorted(map(lambda i: i.url, actual)) == sorted(expected)


@pytest.mark.parametrize(
    'fs_fac, page_path, expected',
    [
        (lambda: mock_fs().withPage('pages/foo'), 'foo.md',
         []),
        ((lambda: mock_fs()
          .withPage('pages/foo')
          .withPage('pages/bar')),
         'foo',
         []),
        ((lambda: mock_fs()
          .withPage('pages/baz')
          .withPage('pages/foo')
          .withPage('pages/foo/more')
          .withPage('pages/foo/even_more')),
         'foo',
         ['/foo/more', '/foo/even_more'])
    ])
def test_linker_children(fs_fac, page_path, expected):
    fs = fs_fac()
    fs.withConfig()
    with mock_fs_scope(fs):
        app = fs.getApp()
        app.config.set('site/pretty_urls', True)
        src = app.getSource('pages')
        item = get_simple_content_item(app, page_path)
        linker = Linker(src, item)
        actual = list(linker.children)
        assert sorted(map(lambda i: i.url, actual)) == sorted(expected)
