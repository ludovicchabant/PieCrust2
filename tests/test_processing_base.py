import pytest
from piecrust.processing.base import ProcessorPipeline
from .mockutil import mock_fs, mock_fs_scope


def _get_pipeline(fs, **kwargs):
    return ProcessorPipeline(fs.getApp(), fs.path('counter'),
            num_workers=1, **kwargs)

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
            .withFile('kitchen/something.html', 'A test file.'))
    with mock_fs_scope(fs):
        pp = _get_pipeline(fs)
        pp.filterProcessors(['copy'])
        expected = {}
        assert expected == fs.getStructure('counter')
        pp.run()
        expected = {'something.html': 'A test file.'}
        assert expected == fs.getStructure('counter')


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
            .withFile('kitchen/something.html', 'A test file.')
            .withFile('kitchen/_hidden.html', 'Shhh')
            .withFile('kitchen/foo/_important.html', 'Important!'))
    with mock_fs_scope(fs):
        pp = _get_pipeline(fs, skip_patterns=['/^_/'])
        pp.filterProcessors(['copy'])
        expected = {}
        assert expected == fs.getStructure('counter')
        pp.run()
        expected = {
                'something.html': 'A test file.',
                'foo': {
                    '_important.html': 'Important!'}
                }
        assert expected == fs.getStructure('counter')

