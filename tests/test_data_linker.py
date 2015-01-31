import pytest
from piecrust.data.linker import Linker, RecursiveLinker
from .mockutil import mock_fs, mock_fs_scope


@pytest.mark.parametrize(
    'fs, page_path, expected',
    [
        (mock_fs().withPage('pages/foo'), 'foo.md',
            [('/foo', True, False)]),
        ((mock_fs()
                .withPage('pages/foo')
                .withPage('pages/bar')),
            'foo.md',
            [('/bar', False, False), ('/foo', True, False)]),
        ((mock_fs()
                .withPage('pages/baz')
                .withPage('pages/something/else')
                .withPage('pages/foo')
                .withPage('pages/bar')),
            'foo.md',
            [('/bar', False, False), ('/baz', False, False),
                ('/foo', True, False), ('something', False, True)]),
        ((mock_fs()
                .withPage('pages/something/else')
                .withPage('pages/foo')
                .withPage('pages/something/good')
                .withPage('pages/bar')),
            'something/else.md',
            [('/something/else', True, False),
                ('/something/good', False, False)])
    ])
def test_linker_iteration(fs, page_path, expected):
    with mock_fs_scope(fs):
        app = fs.getApp()
        src = app.getSource('pages')
        linker = Linker(src, page_path=page_path)
        actual = list(iter(linker))

        assert len(actual) == len(expected)
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert a.is_dir == e[2]
            if a.is_dir:
                assert a.name == e[0]
            else:
                assert a.url == e[0]
                assert a.is_self == e[1]


@pytest.mark.parametrize(
        'fs, page_path, expected',
        [
            (mock_fs().withPage('pages/foo'), 'foo.md',
                [('/foo', True)]),
            ((mock_fs()
                    .withPage('pages/foo')
                    .withPage('pages/bar')),
                'foo.md',
                [('/bar', False), ('/foo', True)]),
            ((mock_fs()
                    .withPage('pages/baz')
                    .withPage('pages/something/else')
                    .withPage('pages/foo')
                    .withPage('pages/bar')),
                'foo.md',
                [('/bar', False), ('/baz', False),
                    ('/foo', True), ('/something/else', False)]),
            ((mock_fs()
                    .withPage('pages/something/else')
                    .withPage('pages/foo')
                    .withPage('pages/something/good')
                    .withPage('pages/bar')),
                'something/else.md',
                [('/something/else', True),
                    ('/something/good', False)])
        ])
def test_recursive_linker_iteration(fs, page_path, expected):
    with mock_fs_scope(fs):
        app = fs.getApp()
        src = app.getSource('pages')
        linker = RecursiveLinker(src, page_path=page_path)
        actual = list(iter(linker))

        assert len(actual) == len(expected)
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert a.is_dir is False
            assert a.url == e[0]
            assert a.is_self == e[1]

