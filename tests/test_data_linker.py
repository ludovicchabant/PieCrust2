import os.path
import pytest
from piecrust.data.linker import Linker
from .mockutil import mock_fs, mock_fs_scope


@pytest.mark.parametrize(
    'fs_fac, page_path, expected',
    [
        (lambda: mock_fs().withPage('pages/foo'), 'foo.md',
            # is_dir, name, is_self, data
            [(False, 'foo', True, '/foo')]),
        ((lambda: mock_fs()
                .withPage('pages/foo')
                .withPage('pages/bar')),
            'foo.md',
            [(False, 'bar', False, '/bar'), (False, 'foo', True, '/foo')]),
        ((lambda: mock_fs()
                .withPage('pages/baz')
                .withPage('pages/something')
                .withPage('pages/something/else')
                .withPage('pages/foo')
                .withPage('pages/bar')),
            'foo.md',
            [(False, 'bar', False, '/bar'),
                (False, 'baz', False, '/baz'),
                (False, 'foo', True, '/foo'),
                (True, 'something', False, '/something')]),
        ((lambda: mock_fs()
                .withPage('pages/something/else')
                .withPage('pages/foo')
                .withPage('pages/something/good')
                .withPage('pages/bar')),
            'something/else.md',
            [(False, 'else', True, '/something/else'),
                (False, 'good', False, '/something/good')])
    ])
def test_linker_iteration(fs_fac, page_path, expected):
    fs = fs_fac()
    fs.withConfig()
    with mock_fs_scope(fs):
        app = fs.getApp()
        app.config.set('site/pretty_urls', True)
        src = app.getSource('pages')
        linker = Linker(src, os.path.dirname(page_path),
                        root_page_path=page_path)
        actual = list(iter(linker))

        assert len(actual) == len(expected)
        for (a, e) in zip(actual, expected):
            is_dir, name, is_self, url = e
            assert a.is_dir == is_dir
            assert a.name == name
            assert a.is_self == is_self
            assert a.url == url


@pytest.mark.parametrize(
        'fs_fac, page_path, expected',
        [
            (lambda: mock_fs().withPage('pages/foo'), 'foo.md',
                [('/foo', True)]),
            ((lambda: mock_fs()
                    .withPage('pages/foo')
                    .withPage('pages/bar')),
                'foo.md',
                [('/bar', False), ('/foo', True)]),
            ((lambda: mock_fs()
                    .withPage('pages/baz')
                    .withPage('pages/something/else')
                    .withPage('pages/foo')
                    .withPage('pages/bar')),
                'foo.md',
                [('/bar', False), ('/baz', False),
                    ('/foo', True), ('/something/else', False)]),
            ((lambda: mock_fs()
                    .withPage('pages/something/else')
                    .withPage('pages/foo')
                    .withPage('pages/something/good')
                    .withPage('pages/bar')),
                'something/else.md',
                [('/something/else', True),
                    ('/something/good', False)])
        ])
def test_recursive_linker_iteration(fs_fac, page_path, expected):
    fs = fs_fac()
    fs.withConfig()
    with mock_fs_scope(fs):
        app = fs.getApp()
        app.config.set('site/pretty_urls', True)
        src = app.getSource('pages')
        linker = Linker(src, os.path.dirname(page_path),
                        root_page_path=page_path)
        actual = list(iter(linker.allpages))

        assert len(actual) == len(expected)
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert a.is_dir is False
            assert a.url == e[0]
            assert a.is_self == e[1]

