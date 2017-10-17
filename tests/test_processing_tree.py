from piecrust.processing.base import SimpleFileProcessor
from piecrust.processing.copy import CopyFileProcessor
from piecrust.pipelines._proctree import (
    ProcessingTreeBuilder, ProcessingTreeNode)


class MockProcessor(SimpleFileProcessor):
    def __init__(self):
        super(MockProcessor, self).__init__({'mock': 'out'})
        self.processed = []

    def _doProcess(self, in_path, out_path):
        self.processed.append((in_path, out_path))


mock_processors = [MockProcessor(), CopyFileProcessor()]
IDX_MOCK = 0
IDX_COPY = 1


def test_mock_node():
    node = ProcessingTreeNode('/foo.mock', list(mock_processors))
    assert node.getProcessor() == mock_processors[IDX_MOCK]


def test_copy_node():
    node = ProcessingTreeNode('/foo.other', list(mock_processors))
    assert node.getProcessor() == mock_processors[IDX_COPY]


def test_build_simple_tree():
    builder = ProcessingTreeBuilder(mock_processors)
    root = builder.build('/foo.mock')
    assert root is not None
    assert root.getProcessor() == mock_processors[IDX_MOCK]
    assert not root.is_leaf
    assert len(root.outputs) == 1
    out = root.outputs[0]
    assert out.getProcessor() == mock_processors[IDX_COPY]

