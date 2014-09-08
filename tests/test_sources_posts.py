import os
import pytest
from .mockutil import mock_fs, mock_fs_scope


@pytest.mark.parametrize('fs, src_type, expected_paths, expected_metadata', [
        (mock_fs(), 'flat', [], []),
        (mock_fs().withPage('test/2014-01-01_foo.md'),
            'flat',
            ['2014-01-01_foo.md'],
            [(2014, 1, 1, 'foo')]),
        (mock_fs(), 'shallow', [], []),
        (mock_fs().withPage('test/2014/01-01_foo.md'),
            'shallow',
            ['2014/01-01_foo.md'],
            [(2014, 1, 1, 'foo')]),
        (mock_fs(), 'hierarchy', [], []),
        (mock_fs().withPage('test/2014/01/01_foo.md'),
            'hierarchy',
            ['2014/01/01_foo.md'],
            [(2014, 1, 1, 'foo')]),
        ])
def test_post_source_factories(fs, src_type, expected_paths, expected_metadata):
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
            app = fs.getApp(cache=False)
            s = app.getSource('test')
            facs = list(s.buildPageFactories())
            paths = [f.rel_path for f in facs]
            assert paths == expected_paths
            metadata = [
                    (f.metadata['year'], f.metadata['month'],
                        f.metadata['day'], f.metadata['slug'])
                    for f in facs]
            assert metadata == expected_metadata

