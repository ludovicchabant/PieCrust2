import time
import os.path
import random
import inspect
import pytest
from piecrust.pipelines.asset import get_filtered_processors
from piecrust.pipelines.records import MultiRecord
from piecrust.processing.base import SimpleFileProcessor
from .mockutil import mock_fs, mock_fs_scope


class FooProcessor(SimpleFileProcessor):
    def __init__(self, name=None, exts=None, open_func=None):
        self.PROCESSOR_NAME = name or 'foo'
        exts = exts or {'foo': 'foo'}
        super().__init__(exts)
        self.open_func = open_func or open

    def _doProcess(self, in_path, out_path):
        with self.open_func(in_path, 'r') as f:
            text = f.read()
        with self.open_func(out_path, 'w') as f:
            f.write("%s: %s" % (self.PROCESSOR_NAME.upper(), text))
        return True


def _get_test_plugin_name():
    return 'foo_%d' % random.randrange(1000)


def _get_test_fs(*, plugins=None, processors=None):
    plugins = plugins or []
    processors = processors or []
    processors.append('copy')
    return (mock_fs()
            .withDir('counter')
            .withConfig({
                'site': {
                    'plugins': plugins
                },
                'pipelines': {
                    'asset': {
                        'processors': processors
                    }
                }
            }))


def _create_test_plugin(fs, plugname, *, foo_name=None, foo_exts=None):
    src = [
        'from piecrust.plugins.base import PieCrustPlugin',
        'from piecrust.processing.base import SimpleFileProcessor']

    foo_lines = inspect.getsourcelines(FooProcessor)
    src += ['']
    src += map(lambda l: l.rstrip('\n'), foo_lines[0])

    src += [
        '',
        'class FooPlugin(PieCrustPlugin):',
        '    def getProcessors(self):',
        '        yield FooProcessor(%s, %s)' % (repr(foo_name),
                                                repr(foo_exts)),
        '',
        '__piecrust_plugin__ = FooPlugin']

    print("Creating plugin with source:\n%s" % '\n'.join(src))
    fs.withFile('kitchen/plugins/%s.py' % plugname, '\n'.join(src))


def _bake_assets(fs):
    fs.runChef('bake', '-p', 'asset', '-o', fs.path('counter'))


def test_empty():
    fs = _get_test_fs()
    with mock_fs_scope(fs):
        expected = {}
        assert expected == fs.getStructure('counter')
        _bake_assets(fs)
        expected = {}
        assert expected == fs.getStructure('counter')


def test_one_file():
    fs = (_get_test_fs()
          .withFile('kitchen/assets/something.foo', 'A test file.'))
    with mock_fs_scope(fs):
        expected = {}
        assert expected == fs.getStructure('counter')
        _bake_assets(fs)
        expected = {'something.foo': 'A test file.'}
        assert expected == fs.getStructure('counter')


def test_one_level_dirtyness():
    fs = (_get_test_fs()
          .withFile('kitchen/assets/blah.foo', 'A test file.'))
    with mock_fs_scope(fs):
        _bake_assets(fs)
        expected = {'blah.foo': 'A test file.'}
        assert expected == fs.getStructure('counter')
        mtime = os.path.getmtime(fs.path('/counter/blah.foo'))
        assert abs(time.time() - mtime) <= 2

        time.sleep(1)
        _bake_assets(fs)
        assert expected == fs.getStructure('counter')
        assert mtime == os.path.getmtime(fs.path('/counter/blah.foo'))

        time.sleep(1)
        fs.withFile('kitchen/assets/blah.foo', 'A new test file.')
        _bake_assets(fs)
        expected = {'blah.foo': 'A new test file.'}
        assert expected == fs.getStructure('counter')
        assert mtime < os.path.getmtime(fs.path('/counter/blah.foo'))


def test_two_levels_dirtyness():
    plugname = _get_test_plugin_name()
    fs = (_get_test_fs(plugins=[plugname], processors=['foo'])
          .withFile('kitchen/assets/blah.foo', 'A test file.'))
    _create_test_plugin(fs, plugname, foo_exts={'foo': 'bar'})
    with mock_fs_scope(fs):
        _bake_assets(fs)
        expected = {'blah.bar': 'FOO: A test file.'}
        assert expected == fs.getStructure('counter')
        mtime = os.path.getmtime(fs.path('/counter/blah.bar'))
        assert abs(time.time() - mtime) <= 2

        time.sleep(1)
        _bake_assets(fs)
        assert expected == fs.getStructure('counter')
        assert mtime == os.path.getmtime(fs.path('/counter/blah.bar'))

        time.sleep(1)
        fs.withFile('kitchen/assets/blah.foo', 'A new test file.')
        _bake_assets(fs)
        expected = {'blah.bar': 'FOO: A new test file.'}
        assert expected == fs.getStructure('counter')
        assert mtime < os.path.getmtime(fs.path('/counter/blah.bar'))


def test_removed():
    fs = (_get_test_fs()
          .withFile('kitchen/assets/blah1.foo', 'A test file.')
          .withFile('kitchen/assets/blah2.foo', 'Ooops'))
    with mock_fs_scope(fs):
        expected = {
            'blah1.foo': 'A test file.',
            'blah2.foo': 'Ooops'}
        assert expected == fs.getStructure('kitchen/assets')
        _bake_assets(fs)
        assert expected == fs.getStructure('counter')

        time.sleep(1)
        os.remove(fs.path('/kitchen/assets/blah2.foo'))
        expected = {
            'blah1.foo': 'A test file.'}
        assert expected == fs.getStructure('kitchen/assets')
        _bake_assets(fs)
        assert expected == fs.getStructure('counter')


def test_record_version_change():
    plugname = _get_test_plugin_name()
    fs = (_get_test_fs(plugins=[plugname], processors=['foo'])
          .withFile('kitchen/assets/blah.foo', 'A test file.'))
    _create_test_plugin(fs, plugname)
    with mock_fs_scope(fs):
        time.sleep(1)
        _bake_assets(fs)
        time.sleep(0.1)
        mtime = os.path.getmtime(fs.path('counter/blah.foo'))

        time.sleep(1)
        _bake_assets(fs)
        time.sleep(0.1)
        assert mtime == os.path.getmtime(fs.path('counter/blah.foo'))

        MultiRecord.RECORD_VERSION += 1
        try:
            time.sleep(1)
            _bake_assets(fs)
            time.sleep(0.1)
            assert mtime < os.path.getmtime(fs.path('counter/blah.foo'))
        finally:
            MultiRecord.RECORD_VERSION -= 1


@pytest.mark.parametrize('patterns, expected', [
    (['_'],
     {'something.html': 'A test file.'}),
    (['html'],
     {}),
    (['/^_/'],
     {'something.html': 'A test file.',
      'foo': {'_important.html': 'Important!'}})
])
def test_ignore_pattern(patterns, expected):
    fs = (_get_test_fs()
          .withFile('kitchen/assets/something.html', 'A test file.')
          .withFile('kitchen/assets/_hidden.html', 'Shhh')
          .withFile('kitchen/assets/foo/_important.html', 'Important!'))
    fs.withConfig({'pipelines': {'asset': {'ignore': patterns}}})
    with mock_fs_scope(fs):
        assert {} == fs.getStructure('counter')
        _bake_assets(fs)
        assert expected == fs.getStructure('counter')


@pytest.mark.parametrize('names, expected', [
    ('all', ['browserify', 'cleancss', 'compass', 'copy', 'concat', 'less',
             'requirejs', 'sass', 'sitemap', 'uglifyjs', 'pygments_style']),
    ('all -sitemap', ['browserify', 'cleancss', 'copy', 'compass', 'concat',
                      'less', 'requirejs', 'sass', 'uglifyjs',
                      'pygments_style']),
    ('-sitemap -less -sass all', ['browserify', 'cleancss', 'copy', 'compass',
                                  'concat', 'requirejs', 'uglifyjs',
                                  'pygments_style']),
    ('copy', ['copy']),
    ('less sass', ['less', 'sass'])
])
def test_filter_processor(names, expected):
    fs = mock_fs().withConfig()
    with mock_fs_scope(fs):
        app = fs.getApp()
        processors = app.plugin_loader.getProcessors()
        procs = get_filtered_processors(processors, names)
        actual = [p.PROCESSOR_NAME for p in procs]
        assert sorted(actual) == sorted(expected)

