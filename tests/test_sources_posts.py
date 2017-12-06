import os.path
import pytest
from .mockutil import mock_fs, mock_fs_scope
from .pathutil import slashfix


@pytest.mark.parametrize(
    'fs_fac, src_type, expected_paths, expected_metadata',
    [
        (lambda: mock_fs(), 'flat', [], []),
        (lambda: mock_fs().withPage('test/2014-01-01_foo.md'),
            'flat',
            ['2014-01-01_foo.md'],
            [(2014, 1, 1, 'foo')]),
        (lambda: mock_fs(), 'shallow', [], []),
        (lambda: mock_fs().withPage('test/2014/01-01_foo.md'),
            'shallow',
            ['2014/01-01_foo.md'],
            [(2014, 1, 1, 'foo')]),
        (lambda: mock_fs(), 'hierarchy', [], []),
        (lambda: mock_fs().withPage('test/2014/01/01_foo.md'),
            'hierarchy',
            ['2014/01/01_foo.md'],
            [(2014, 1, 1, 'foo')]),
    ])
def test_post_source_items(fs_fac, src_type, expected_paths,
                           expected_metadata):
    fs = fs_fac()
    fs.withConfig({
        'site': {
            'sources': {
                'test': {'type': 'posts/%s' % src_type}},
            'routes': [
                {'url': '/%slug%', 'source': 'test'}]
        }
    })
    fs.withDir('kitchen/test')
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        items = list(s.getAllContents())
        paths = [os.path.relpath(f.spec, s.fs_endpoint_path) for f in items]
        assert paths == slashfix(expected_paths)
        metadata = [
            (f.metadata['route_params']['year'],
             f.metadata['route_params']['month'],
             f.metadata['route_params']['day'],
             f.metadata['route_params']['slug'])
            for f in items]
        assert metadata == expected_metadata

