import os
import pytest
from piecrust.app import PieCrust
from piecrust.sources.pageref import PageRef, PageNotFoundError
from .mockutil import mock_fs, mock_fs_scope
from .pathutil import slashfix


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


@pytest.mark.parametrize('page_ref, expected_source_name, expected_rel_path, '
                         'expected_possible_paths', [
        ('foo:one.md', 'foo', 'one.md',
            ['foo/one.md']),
        ('foo:two.md', 'foo', 'two.md',
            ['foo/two.md']),
        ('foo:two.html', 'foo', 'two.html',
            ['foo/two.html']),
        ('foo:two.%ext%', 'foo', 'two.html',
            ['foo/two.html', 'foo/two.md', 'foo/two.textile']),
        ('foo:subdir/four.md', 'foo', 'subdir/four.md',
            ['foo/subdir/four.md']),
        ('foo:subdir/four.%ext%', 'foo', 'subdir/four.md',
            ['foo/subdir/four.html', 'foo/subdir/four.md',
             'foo/subdir/four.textile']),
        ('foo:three.md;bar:three.md', 'foo', 'three.md',
            ['foo/three.md', 'bar/three.md']),
        ('foo:three.%ext%;bar:three.%ext%', 'foo', 'three.md',
            ['foo/three.html', 'foo/three.md', 'foo/three.textile',
             'bar/three.html', 'bar/three.md', 'bar/three.textile']),
        ('foo:special.md;bar:special.md', 'bar', 'special.md',
            ['foo/special.md', 'bar/special.md'])
        ])
def test_page_ref(page_ref, expected_source_name, expected_rel_path,
                  expected_possible_paths):
    fs = (mock_fs()
            .withConfig({
                'site': {
                    'sources': {
                        'foo': {},
                        'bar': {}
                        }
                    }
                })
            .withPage('foo/one.md')
            .withPage('foo/two.md')
            .withPage('foo/two.html')
            .withPage('foo/three.md')
            .withPage('foo/subdir/four.md')
            .withPage('bar/three.md')
            .withPage('bar/special.md'))
    with mock_fs_scope(fs):
        app = fs.getApp()
        r = PageRef(app, page_ref)

        assert r.possible_paths == slashfix(
                [os.path.join(fs.path('/kitchen'), p)
                    for p in expected_possible_paths])

        assert r.exists
        assert r.source_name == expected_source_name
        assert r.source == app.getSource(expected_source_name)
        assert r.rel_path == expected_rel_path
        assert r.path == slashfix(fs.path(os.path.join(
                'kitchen', expected_source_name, expected_rel_path)))


def test_page_ref_with_missing_source():
    fs = mock_fs()
    with mock_fs_scope(fs):
        app = fs.getApp()
        r = PageRef(app, 'whatever:doesnt_exist.md')
        with pytest.raises(Exception):
            r.possible_rel_paths


def test_page_ref_with_missing_file():
    fs = mock_fs()
    with mock_fs_scope(fs):
        app = fs.getApp()
        r = PageRef(app, 'pages:doesnt_exist.%ext%')
        assert r.possible_rel_paths == [
                'doesnt_exist.html', 'doesnt_exist.md', 'doesnt_exist.textile']
        assert r.source_name == 'pages'
        with pytest.raises(PageNotFoundError):
            r.rel_path
        with pytest.raises(PageNotFoundError):
            r.path
        assert not r.exists

