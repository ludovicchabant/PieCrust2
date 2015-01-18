import time
import os.path
import shutil
import pytest
from piecrust.processing.base import (ProcessorPipeline, SimpleFileProcessor)
from piecrust.processing.records import ProcessorPipelineRecord
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


def _get_pipeline(fs, app=None):
    app = app or fs.getApp()
    app.config.set('baker/num_workers', 1)
    return ProcessorPipeline(app, fs.path('counter'))


def test_empty():
    fs = mock_fs()
    with mock_fs_scope(fs):
        pp = _get_pipeline(fs)
        pp.filterProcessors(['copy'])
        expected = {}
        assert expected == fs.getStructure('counter')
        pp.run()
        expected = {}
        assert expected == fs.getStructure('counter')


def test_one_file():
    fs = (mock_fs()
            .withFile('kitchen/assets/something.html', 'A test file.'))
    with mock_fs_scope(fs):
        pp = _get_pipeline(fs)
        pp.filterProcessors(['copy'])
        expected = {}
        assert expected == fs.getStructure('counter')
        pp.run()
        expected = {'something.html': 'A test file.'}
        assert expected == fs.getStructure('counter')


def test_one_level_dirtyness():
    fs = (mock_fs()
            .withFile('kitchen/assets/blah.foo', 'A test file.'))
    with mock_fs_scope(fs):
        pp = _get_pipeline(fs)
        pp.filterProcessors(['copy'])
        pp.run()
        expected = {'blah.foo': 'A test file.'}
        assert expected == fs.getStructure('counter')
        mtime = os.path.getmtime(fs.path('/counter/blah.foo'))
        assert abs(time.time() - mtime) <= 2

        pp.run()
        assert expected == fs.getStructure('counter')
        assert mtime == os.path.getmtime(fs.path('/counter/blah.foo'))

        fs.withFile('kitchen/assets/blah.foo', 'A new test file.')
        pp.run()
        expected = {'blah.foo': 'A new test file.'}
        assert expected == fs.getStructure('counter')
        assert mtime < os.path.getmtime(fs.path('/counter/blah.foo'))


def test_two_levels_dirtyness():
    fs = (mock_fs()
            .withFile('kitchen/assets/blah.foo', 'A test file.'))
    with mock_fs_scope(fs) as scope:
        pp = _get_pipeline(fs)
        pp.processors.append(FooProcessor(('foo', 'bar'), scope._open))
        pp.filterProcessors(['foo', 'copy'])
        pp.run()
        expected = {'blah.bar': 'FOO: A test file.'}
        assert expected == fs.getStructure('counter')
        mtime = os.path.getmtime(fs.path('/counter/blah.bar'))
        assert abs(time.time() - mtime) <= 2

        pp.run()
        assert expected == fs.getStructure('counter')
        assert mtime == os.path.getmtime(fs.path('/counter/blah.bar'))

        fs.withFile('kitchen/assets/blah.foo', 'A new test file.')
        pp.run()
        expected = {'blah.bar': 'FOO: A new test file.'}
        assert expected == fs.getStructure('counter')
        assert mtime < os.path.getmtime(fs.path('/counter/blah.bar'))


def test_removed():
    fs = (mock_fs()
            .withFile('kitchen/assets/blah1.foo', 'A test file.')
            .withFile('kitchen/assets/blah2.foo', 'Ooops'))
    with mock_fs_scope(fs):
        expected = {
                'blah1.foo': 'A test file.',
                'blah2.foo': 'Ooops'}
        assert expected == fs.getStructure('kitchen/assets')
        pp = _get_pipeline(fs)
        pp.filterProcessors(['copy'])
        pp.run()
        assert expected == fs.getStructure('counter')

        os.remove(fs.path('/kitchen/assets/blah2.foo'))
        expected = {
                'blah1.foo': 'A test file.'}
        assert expected == fs.getStructure('kitchen/assets')
        pp.run()
        assert expected == fs.getStructure('counter')


def test_record_version_change():
    fs = (mock_fs()
            .withFile('kitchen/assets/blah.foo', 'A test file.'))
    with mock_fs_scope(fs):
        pp = _get_pipeline(fs)
        noop = NoopProcessor(('foo', 'foo'))
        pp.processors.append(noop)
        pp.filterProcessors(['foo', 'copy'])
        pp.run()
        assert 1 == len(noop.processed)

        pp.run()
        assert 1 == len(noop.processed)

        ProcessorPipelineRecord.RECORD_VERSION += 1
        try:
            pp.run()
            assert 2 == len(noop.processed)
        finally:
            ProcessorPipelineRecord.RECORD_VERSION -= 1


@pytest.mark.parametrize('patterns, expected', [
        (['_'],
            {'something.html': 'A test file.'}),
        (['html'],
            {}),
        (['/^_/'],
            {'something.html': 'A test file.',
                'foo': {'_important.html': 'Important!'}})
        ])
def test_skip_pattern(patterns, expected):
    fs = (mock_fs()
            .withFile('kitchen/assets/something.html', 'A test file.')
            .withFile('kitchen/assets/_hidden.html', 'Shhh')
            .withFile('kitchen/assets/foo/_important.html', 'Important!'))
    with mock_fs_scope(fs):
        pp = _get_pipeline(fs)
        pp.addSkipPatterns(patterns)
        pp.filterProcessors(['copy'])
        assert {} == fs.getStructure('counter')
        pp.run()
        assert expected == fs.getStructure('counter')


@pytest.mark.parametrize('names, expected', [
        ('all', ['copy', 'concat', 'less', 'sass', 'sitemap']),
        ('all -sitemap', ['copy', 'concat', 'less', 'sass']),
        ('-sitemap -less -sass all', ['copy', 'concat']),
        ('copy', ['copy']),
        ('less sass', ['less', 'sass'])
    ])
def test_filter_processor(names, expected):
    fs = mock_fs()
    with mock_fs_scope(fs):
        app = fs.getApp()
        pp = _get_pipeline(fs, app=app)
        pp.filterProcessors('copy concat less sass sitemap')
        procs = pp.getFilteredProcessors(names)
        actual = [p.PROCESSOR_NAME for p in procs]
        assert sorted(actual) == sorted(expected)

