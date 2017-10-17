import time
import os.path
import shutil
import inspect
import pytest
from piecrust.pipelines.asset import get_filtered_processors
from piecrust.pipelines.records import MultiRecord
from piecrust.processing.base import SimpleFileProcessor
from .mockutil import mock_fs, mock_fs_scope


class FooProcessor(SimpleFileProcessor):
    def __init__(self, exts=None, open_func=None):
        exts = exts or {'foo', 'foo'}
        super(FooProcessor, self).__init__({exts[0]: exts[1]})
        self.PROCESSOR_NAME = exts[0]
        self.open_func = open_func or open

    def _doProcess(self, in_path, out_path):
        with self.open_func(in_path, 'r') as f:
            text = f.read()
        with self.open_func(out_path, 'w') as f:
            f.write("%s: %s" % (self.PROCESSOR_NAME.upper(), text))
        return True


class NoopProcessor(SimpleFileProcessor):
    def __init__(self, exts):
        super(NoopProcessor, self).__init__({exts[0]: exts[1]})
        self.PROCESSOR_NAME = exts[0]
        self.processed = []

    def _doProcess(self, in_path, out_path):
        self.processed.append(in_path)
        shutil.copyfile(in_path, out_path)
        return True


def _get_test_fs(processors=None):
    if processors is None:
        processors = 'copy'
    return (mock_fs()
            .withDir('counter')
            .withConfig({
                'pipelines': {
                    'asset': {
                        'processors': processors
                    }
                }
            }))


def _create_test_plugin(fs, *, foo_exts=None, noop_exts=None):
    src = [
        'from piecrust.plugins.base import PieCrustPlugin',
        'from piecrust.processing.base import SimpleFileProcessor']

    foo_lines = inspect.getsourcelines(FooProcessor)
    src += ['']
    src += map(lambda l: l.rstrip('\n'), foo_lines[0])

    noop_lines = inspect.getsourcelines(NoopProcessor)
    src += ['']
    src += map(lambda l: l.rstrip('\n'), noop_lines[0])

    src += [
        '',
        'class FooNoopPlugin(PieCrustPlugin):',
        '    def getProcessors(self):',
        '        yield FooProcessor(%s)' % repr(foo_exts),
        '        yield NoopProcessor(%s)' % repr(noop_exts),
        '',
        '__piecrust_plugin__ = FooNoopPlugin']

    fs.withFile('kitchen/plugins/foonoop.py', src)


def _bake_assets(fs):
    fs.runChef('bake', '-p', 'asset')


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
          .withFile('kitchen/assets/something.html', 'A test file.'))
    with mock_fs_scope(fs):
        expected = {}
        assert expected == fs.getStructure('counter')
        _bake_assets(fs)
        expected = {'something.html': 'A test file.'}
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
    fs = (_get_test_fs()
          .withFile('kitchen/assets/blah.foo', 'A test file.'))
    _create_test_plugin(fs, foo_exts=('foo', 'bar'))
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
        _bake_assets(1)
        assert expected == fs.getStructure('counter')


def test_record_version_change():
    fs = (_get_test_fs()
          .withFile('kitchen/assets/blah.foo', 'A test file.'))
    _create_test_plugin(fs, foo_exts=('foo', 'foo'))
    with mock_fs_scope(fs):
        _bake_assets(fs)
        assert os.path.exists(fs.path('/counter/blah.foo')) is True
        mtime = os.path.getmtime(fs.path('/counter/blah.foo'))

        time.sleep(1)
        _bake_assets(fs)
        assert mtime == os.path.getmtime(fs.path('/counter/blah.foo'))

        time.sleep(1)
        MultiRecord.RECORD_VERSION += 1
        try:
            _bake_assets(fs)
            assert mtime < os.path.getmtime(fs.path('/counter/blah.foo'))
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
    ('all', ['cleancss', 'compass', 'copy', 'concat', 'less', 'requirejs',
             'sass', 'sitemap', 'uglifyjs', 'pygments_style']),
    ('all -sitemap', ['cleancss', 'copy', 'compass', 'concat', 'less',
                      'requirejs', 'sass', 'uglifyjs', 'pygments_style']),
    ('-sitemap -less -sass all', ['cleancss', 'copy', 'compass', 'concat',
                                  'requirejs', 'uglifyjs',
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

