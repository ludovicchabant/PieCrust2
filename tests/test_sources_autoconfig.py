import os.path
import pytest
from .mockutil import mock_fs, mock_fs_scope
from .pathutil import slashfix


@pytest.mark.parametrize(
    'fs_fac, src_config, expected_paths, expected_metadata',
    [
        (lambda: mock_fs(), {}, [], []),
        (lambda: mock_fs().withPage('test/_index.md'),
         {},
         ['_index.md'],
         [{'slug': '', 'config': {'foo': []}}]),
        (lambda: mock_fs().withPage('test/something.md'),
         {},
         ['something.md'],
         [{'slug': 'something', 'config': {'foo': []}}]),
        (lambda: mock_fs().withPage('test/bar/something.md'),
         {},
         ['bar/something.md'],
         [{'slug': 'something', 'config': {'foo': ['bar']}}]),
        (lambda: mock_fs().withPage('test/bar1/bar2/something.md'),
         {},
         ['bar1/bar2/something.md'],
         [{'slug': 'something', 'config': {'foo': ['bar1', 'bar2']}}]),

        (lambda: mock_fs().withPage('test/something.md'),
         {'collapse_single_values': True},
         ['something.md'],
         [{'slug': 'something', 'config': {'foo': None}}]),
        (lambda: mock_fs().withPage('test/bar/something.md'),
         {'collapse_single_values': True},
         ['bar/something.md'],
         [{'slug': 'something', 'config': {'foo': 'bar'}}]),
        (lambda: mock_fs().withPage('test/bar1/bar2/something.md'),
         {'collapse_single_values': True},
         ['bar1/bar2/something.md'],
         [{'slug': 'something', 'config': {'foo': ['bar1', 'bar2']}}]),

        (lambda: mock_fs().withPage('test/something.md'),
         {'only_single_values': True},
         ['something.md'],
         [{'slug': 'something', 'config': {'foo': None}}]),
        (lambda: mock_fs().withPage('test/bar/something.md'),
         {'only_single_values': True},
         ['bar/something.md'],
         [{'slug': 'something', 'config': {'foo': 'bar'}}]),
    ])
def test_autoconfig_source_factories(fs_fac, src_config, expected_paths,
                                     expected_metadata):
    site_config = {
        'sources': {
            'test': {'type': 'autoconfig',
                     'setting_name': 'foo'}
        },
        'routes': [
            {'url': '/%slug%', 'source': 'test'}]
    }
    site_config['sources']['test'].update(src_config)
    fs = fs_fac()
    fs.withConfig({'site': site_config})
    fs.withDir('kitchen/test')
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        items = list(s.getAllContents())
        paths = [os.path.relpath(i.spec, s.fs_endpoint_path) for i in items]
        assert paths == slashfix(expected_paths)
        metadata = [i.metadata['route_params'] for i in items]
        assert metadata == expected_metadata


def test_autoconfig_fails_if_multiple_folders():
    site_config = {
        'sources': {
            'test': {'type': 'autoconfig',
                     'setting_name': 'foo',
                     'only_single_values': True}
        }
    }
    fs = mock_fs().withConfig({'site': site_config})
    fs.withPage('test/bar1/bar2/something.md')
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        with pytest.raises(Exception):
            list(s.getAllContents())


@pytest.mark.parametrize(
    'fs_fac, expected_paths, expected_metadata',
    [
        (lambda: mock_fs(), [], []),
        (lambda: mock_fs().withPage('test/_index.md'),
         ['_index.md'],
         [{'slug': '',
           'config': {'foo': 0, 'foo_trail': [0]}}]),
        (lambda: mock_fs().withPage('test/something.md'),
         ['something.md'],
         [{'slug': 'something',
           'config': {'foo': 0, 'foo_trail': [0]}}]),
        (lambda: mock_fs().withPage('test/08_something.md'),
         ['08_something.md'],
         [{'slug': 'something',
           'config': {'foo': 8, 'foo_trail': [8]}}]),
        (lambda: mock_fs().withPage('test/02_there/08_something.md'),
         ['02_there/08_something.md'],
         [{'slug': 'there/something',
           'config': {'foo': 8, 'foo_trail': [2, 8]}}]),
    ])
def test_ordered_source_factories(fs_fac, expected_paths, expected_metadata):
    site_config = {
        'sources': {
            'test': {'type': 'ordered',
                     'setting_name': 'foo'}
        },
        'routes': [
            {'url': '/%slug%', 'source': 'test'}]
    }
    fs = fs_fac()
    fs.withConfig({'site': site_config})
    fs.withDir('kitchen/test')
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        facs = list(s.buildPageFactories())
        paths = [f.rel_path for f in facs]
        assert paths == slashfix(expected_paths)
        metadata = [f.metadata for f in facs]
        assert metadata == expected_metadata


@pytest.mark.parametrize(
    'fs_fac, route_path, expected_path, expected_metadata',
    [
        (lambda: mock_fs(), 'missing', None, None),
        (lambda: mock_fs().withPage('test/something.md'),
         'something', 'something.md',
         {'slug': 'something',
          'config': {'foo': 0, 'foo_trail': [0]}}),
        (lambda: mock_fs().withPage('test/bar/something.md'),
         'bar/something', 'bar/something.md',
         {'slug': 'bar/something',
          'config': {'foo': 0, 'foo_trail': [0]}}),
        (lambda: mock_fs().withPage('test/42_something.md'),
         'something', '42_something.md',
         {'slug': 'something',
          'config': {'foo': 42, 'foo_trail': [42]}}),
        (lambda: mock_fs().withPage('test/bar/42_something.md'),
         'bar/something', 'bar/42_something.md',
         {'slug': 'bar/something',
          'config': {'foo': 42, 'foo_trail': [42]}}),

        ((lambda: mock_fs()
          .withPage('test/42_something.md')
          .withPage('test/43_other_something.md')),
         'something', '42_something.md',
         {'slug': 'something',
          'config': {'foo': 42, 'foo_trail': [42]}}),
    ])
def test_ordered_source_find(fs_fac, route_path, expected_path,
                             expected_metadata):
    site_config = {
        'sources': {
            'test': {'type': 'ordered',
                     'setting_name': 'foo'}
        },
        'routes': [
            {'url': '/%slug%', 'source': 'test'}]
    }
    fs = fs_fac()
    fs.withConfig({'site': site_config})
    fs.withDir('kitchen/test')
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        route_metadata = {'slug': route_path}
        factory = s.findContent(route_metadata)
        if factory is None:
            assert expected_path is None and expected_metadata is None
            return
        assert factory.rel_path == slashfix(expected_path)
        assert factory.metadata == expected_metadata

