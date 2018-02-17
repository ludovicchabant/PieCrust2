import os.path
import pytest
from .mockutil import mock_fs, mock_fs_scope
from .pathutil import slashfix


@pytest.mark.parametrize(
    'fs_fac, src_config, expected_path, expected_slug, expected_foos',
    [
        (lambda: mock_fs(),
         {},
         None, '', []),
        (lambda: mock_fs().withPage('test/_index.md'),
         {},
         '_index.md', '', []),
        (lambda: mock_fs().withPage('test/something.md'),
         {},
         'something.md', 'something', []),
        (lambda: mock_fs().withPage('test/bar/something.md'),
         {},
         'bar/something.md', 'something', ['bar']),
        (lambda: mock_fs().withPage('test/bar1/bar2/something.md'),
         {},
         'bar1/bar2/something.md', 'something', ['bar1', 'bar2']),

        (lambda: mock_fs().withPage('test/something.md'),
         {'collapse_single_values': True},
         'something.md', 'something', None),
        (lambda: mock_fs().withPage('test/bar/something.md'),
         {'collapse_single_values': True},
         'bar/something.md', 'something', 'bar'),
        (lambda: mock_fs().withPage('test/bar1/bar2/something.md'),
         {'collapse_single_values': True},
         'bar1/bar2/something.md', 'something', ['bar1', 'bar2']),

        (lambda: mock_fs().withPage('test/something.md'),
         {'only_single_values': True},
         'something.md', 'something', None),
        (lambda: mock_fs().withPage('test/bar/something.md'),
         {'only_single_values': True},
         'bar/something.md', 'something', 'bar')
    ])
def test_autoconfig_source_items(
        fs_fac, src_config, expected_path, expected_slug, expected_foos):
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

        if expected_path is None:
            assert len(items) == 0
        else:
            assert len(items) == 1
            path = os.path.relpath(items[0].spec, s.fs_endpoint_path)
            assert path == slashfix(expected_path)
            slug = items[0].metadata['route_params']['slug']
            assert slug == expected_slug
            foos = items[0].metadata['config']['foo']
            assert foos == expected_foos


def test_autoconfig_fails_if_multiple_folders():
    site_config = {
        'sources': {
            'test': {'type': 'autoconfig',
                     'setting_name': 'foo',
                     'only_single_values': True}
        },
        'routes': [
            {'url': '/blah', 'source': 'test'}
        ]
    }
    fs = mock_fs().withConfig({'site': site_config})
    fs.withPage('test/bar1/bar2/something.md')
    with mock_fs_scope(fs):
        app = fs.getApp()
        s = app.getSource('test')
        with pytest.raises(Exception):
            list(s.getAllContents())


@pytest.mark.parametrize(
    'fs_fac, expected_paths, expected_route_params, expected_configs',
    [
        (lambda: mock_fs(), [], [], []),
        (lambda: mock_fs().withPage('test/_index.md'),
         ['_index.md'],
         [{'slug': ''}],
         [{'foo': 0, 'foo_trail': [0]}]),
        (lambda: mock_fs().withPage('test/something.md'),
         ['something.md'],
         [{'slug': 'something'}],
         [{'foo': 0, 'foo_trail': [0]}]),
        (lambda: mock_fs().withPage('test/08_something.md'),
         ['08_something.md'],
         [{'slug': 'something'}],
         [{'foo': 8, 'foo_trail': [8]}]),
        (lambda: mock_fs().withPage('test/02_there/08_something.md'),
         ['02_there/08_something.md'],
         [{'slug': 'there/something'}],
         [{'foo': 8, 'foo_trail': [2, 8]}]),
    ])
def test_ordered_source_items(fs_fac, expected_paths, expected_route_params,
                              expected_configs):
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
        items = list(s.getAllContents())

        paths = [os.path.relpath(f.spec, s.fs_endpoint_path) for f in items]
        assert paths == slashfix(expected_paths)
        metadata = [f.metadata['route_params'] for f in items]
        assert metadata == expected_route_params
        configs = [f.metadata['config'] for f in items]
        for c in configs:
            c.pop('format')
        assert configs == expected_configs


@pytest.mark.parametrize(
    'fs_fac, route_path, expected_path, expected_metadata',
    [
        (
            lambda: mock_fs(),
            'missing',
            None,
            None),
        (
            lambda: mock_fs().withPage('test/something.html'),
            'something',
            'something.html',
            {'route_params': {'slug': 'something'},
             'config': {'foo': 0, 'foo_trail': [0]}}),
        (
            lambda: mock_fs().withPage('test/bar/something.html'),
            'bar/something',
            'bar/something.html',
            {'route_params': {'slug': 'bar/something'},
             'config': {'foo': 0, 'foo_trail': [0]}}),
        (
            lambda: mock_fs().withPage('test/42_something.html'),
            'something',
            '42_something.html',
            {'route_params': {'slug': 'something'},
             'config': {'foo': 42, 'foo_trail': [42]}}),
        (
            lambda: mock_fs().withPage('test/bar/42_something.html'),
            'bar/something',
            'bar/42_something.html',
            {'route_params': {'slug': 'bar/something'},
             'config': {'foo': 42, 'foo_trail': [42]}}),
        (
            (lambda: mock_fs()
             .withPage('test/42_something.html')
             .withPage('test/43_other_something.html')),
            'something',
            '42_something.html',
            {'route_params': {'slug': 'something'},
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
        item = s.findContentFromRoute(route_metadata)
        if item is None:
            assert expected_path is None and expected_metadata is None
        else:
            assert os.path.relpath(item.spec, s.fs_endpoint_path) == \
                slashfix(expected_path)
            assert item.metadata == expected_metadata

