import os
import pytest
from piecrust.app import PieCrust
from piecrust.sources.base import DefaultPageSource
from .mockutil import mock_fs, mock_fs_scope


@pytest.mark.parametrize('fs, expected_paths, expected_slugs', [
        (mock_fs(), [], []),
        (mock_fs().withPage('test/foo.html'),
            ['foo.html'], ['foo']),
        (mock_fs().withPage('test/foo.md'),
            ['foo.md'], ['foo']),
        (mock_fs().withPage('test/foo.ext'),
            ['foo.ext'], ['foo.ext']),
        (mock_fs().withPage('test/foo/bar.html'),
            ['foo/bar.html'], ['foo/bar']),
        (mock_fs().withPage('test/foo/bar.md'),
            ['foo/bar.md'], ['foo/bar']),
        (mock_fs().withPage('test/foo/bar.ext'),
            ['foo/bar.ext'], ['foo/bar.ext']),
        ])
def test_default_source_factories(fs, expected_paths, expected_slugs):
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
        slugs = [f.metadata['path'] for f in facs]
        assert slugs == expected_slugs



@pytest.mark.parametrize('ref_path, expected', [
        ('foo.html', '/kitchen/test/foo.html'),
        ('foo/bar.html', '/kitchen/test/foo/bar.html'),
        ])
def test_default_source_resolve_ref(ref_path, expected):
    fs = mock_fs()
    fs.withConfig({
        'site': {
            'sources': {
                'test': {}},
            'routes': [
                {'url': '/%path%', 'source': 'test'}]
            }
        })
    expected = fs.path(expected).replace('/', os.sep)
    with mock_fs_scope(fs):
        app = PieCrust(fs.path('kitchen'), cache=False)
        s = app.getSource('test')
        actual = s.resolveRef(ref_path)
        assert actual == expected

