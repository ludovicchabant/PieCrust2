import os
import pytest
from .mockutil import mock_fs, mock_fs_scope
from .pathutil import slashfix


@pytest.mark.parametrize('fs_fac, expected_paths, expected_slugs', [
    (lambda: mock_fs(), [], []),
    (lambda: mock_fs().withPage('test/foo.html'),
     ['foo.html'], ['foo']),
    (lambda: mock_fs().withPage('test/foo.md'),
     ['foo.md'], ['foo']),
    (lambda: mock_fs().withPage('test/foo.ext'),
     ['foo.ext'], ['foo.ext']),
    (lambda: mock_fs().withPage('test/foo/bar.html'),
     ['foo/bar.html'], ['foo/bar']),
    (lambda: mock_fs().withPage('test/foo/bar.md'),
     ['foo/bar.md'], ['foo/bar']),
    (lambda: mock_fs().withPage('test/foo/bar.ext'),
     ['foo/bar.ext'], ['foo/bar.ext']),
])
def test_default_source_items(fs_fac, expected_paths, expected_slugs):
    fs = fs_fac()
    fs.withConfig({
        'site': {
            'sources': {
                'test': {}},
            'routes': [
                {'url': '/%path%', 'source': 'test'}]
        }
    })
    fs.withDir('kitchen/test')
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        items = list(s.getAllContents())
        paths = [os.path.relpath(f.spec, s.fs_endpoint_path) for f in items]
        assert paths == slashfix(expected_paths)
        slugs = [f.metadata['route_params']['slug'] for f in items]
        assert slugs == expected_slugs


@pytest.mark.parametrize(
    'fs_fac, ref_path, expected_path, expected_metadata', [
        (lambda: mock_fs().withPage('test/foo.html'),
         'foo.html',
         'test/foo.html',
         {'slug': 'foo'}),
        (lambda: mock_fs().withPage('test/foo/bar.html'),
         'foo/bar.html',
         'test/foo/bar.html',
         {'slug': 'foo/bar'}),

    ])
def test_default_source_find_item(fs_fac, ref_path, expected_path,
                                  expected_metadata):
    fs = fs_fac()
    fs.withConfig({
        'site': {
            'sources': {
                'test': {}},
            'routes': [
                {'url': '/%path%', 'source': 'test'}]
        }
    })
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        item = s.findContentFromRoute({'slug': ref_path})
        assert item is not None
        assert os.path.relpath(item.spec, app.root_dir) == \
            slashfix(expected_path)
        assert item.metadata['route_params'] == expected_metadata
