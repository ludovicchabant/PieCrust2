import os
import pytest
from piecrust.app import PieCrust
from .mockutil import mock_fs, mock_fs_scope


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
def test_default_source_factories(fs_fac, expected_paths, expected_slugs):
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
        app = PieCrust(fs.path('kitchen'), cache=False)
        s = app.getSource('test')
        facs = list(s.buildPageFactories())
        paths = [f.rel_path for f in facs]
        assert paths == expected_paths
        slugs = [f.metadata['slug'] for f in facs]
        assert slugs == expected_slugs


@pytest.mark.parametrize(
    'ref_path, expected_path, expected_metadata',
    [
        ('foo.html', '/kitchen/test/foo.html', {'slug': 'foo'}),
        ('foo/bar.html', '/kitchen/test/foo/bar.html',
         {'slug': 'foo/bar'}),
    ])
def test_default_source_resolve_ref(ref_path, expected_path,
                                    expected_metadata):
    fs = mock_fs()
    fs.withConfig({
        'site': {
            'sources': {
                'test': {}},
            'routes': [
                {'url': '/%path%', 'source': 'test'}]
        }
    })
    expected_path = fs.path(expected_path).replace('/', os.sep)
    with mock_fs_scope(fs):
        app = PieCrust(fs.path('kitchen'), cache=False)
        s = app.getSource('test')
        actual_path, actual_metadata = s.resolveRef(ref_path)
        assert actual_path == expected_path
        assert actual_metadata == expected_metadata
