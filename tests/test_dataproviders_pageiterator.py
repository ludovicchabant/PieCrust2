import mock
from piecrust.dataproviders.pageiterator import PageIterator
from piecrust.page import Page, PageConfiguration


def test_skip():
    it = PageIterator(range(12))
    it.skip(5)
    assert it.total_count == 12
    assert len(it) == 7
    assert list(it) == list(range(5, 12))


def test_limit():
    it = PageIterator(range(12))
    it.limit(4)
    assert it.total_count == 12
    assert len(it) == 4
    assert list(it) == list(range(4))


def test_slice():
    it = PageIterator(range(12))
    it.slice(3, 4)
    assert it.total_count == 12
    assert len(it) == 4
    assert list(it) == list(range(3, 7))


def test_natural_sort():
    it = PageIterator([4, 3, 1, 2, 0])
    it.sort()
    assert it.total_count == 5
    assert len(it) == 5
    assert list(it) == list(range(5))


def test_natural_sort_reversed():
    it = PageIterator([4, 3, 1, 2, 0])
    it.sort(reverse=True)
    assert it.total_count == 5
    assert len(it) == 5
    assert list(it) == list(reversed(range(5)))


class _TestItem(object):
    def __init__(self, value):
        self.name = str(value)
        self.config = {'foo': value}

    def __eq__(self, other):
        return other.name == self.name


def test_setting_sort():
    it = PageIterator([_TestItem(v) for v in [4, 3, 1, 2, 0]])
    it.sort('foo')
    assert it.total_count == 5
    assert len(it) == 5
    assert list(it) == [_TestItem(v) for v in range(5)]


def test_setting_sort_reversed():
    it = PageIterator([_TestItem(v) for v in [4, 3, 1, 2, 0]])
    it.sort('foo', reverse=True)
    assert it.total_count == 5
    assert len(it) == 5
    assert list(it) == [_TestItem(v) for v in reversed(range(5))]


def test_filter():
    page = mock.MagicMock(spec=Page)
    page.config = PageConfiguration()
    page.config.set('threes', {'is_foo': 3})
    it = PageIterator([_TestItem(v) for v in [3, 2, 3, 1, 4, 3]],
                      current_page=page)
    it.filter('threes')
    assert it.total_count == 3
    assert len(it) == 3
    assert list(it) == [_TestItem(3), _TestItem(3), _TestItem(3)]


def test_magic_filter():
    it = PageIterator([_TestItem(v) for v in [3, 2, 3, 1, 4, 3]])
    it.is_foo(3)
    assert it.total_count == 3
    assert len(it) == 3
    assert list(it) == [_TestItem(3), _TestItem(3), _TestItem(3)]

