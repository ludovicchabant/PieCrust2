import datetime
import pytest
from piecrust.fastpickle import pickle, unpickle, pickle_obj, unpickle_obj


class Foo(object):
    def __init__(self, name):
        self.name = name
        self.bars = []


class Bar(object):
    def __init__(self, value):
        self.value = value


@pytest.mark.parametrize(
        'obj, expected',
        [
            (True, True),
            (42, 42),
            (3.14, 3.14),
            (datetime.date(2015, 5, 21), datetime.date(2015, 5, 21)),
            (datetime.datetime(2015, 5, 21, 12, 55, 32),
                datetime.datetime(2015, 5, 21, 12, 55, 32)),
            (datetime.time(9, 25, 57), datetime.time(9, 25, 57)),
            ((1, 2, 3), (1, 2, 3)),
            ([1, 2, 3], [1, 2, 3]),
            ({'foo': 1, 'bar': 2}, {'foo': 1, 'bar': 2}),
            (set([1, 2, 3]), set([1, 2, 3])),
            ({'foo': [1, 2, 3], 'bar': {'one': 1, 'two': 2}},
                {'foo': [1, 2, 3], 'bar': {'one': 1, 'two': 2}})
            ])
def test_pickle_unpickle(obj, expected):
    data = pickle(obj)
    actual = unpickle(data)
    assert actual == expected


def test_objects():
    f = Foo('foo')
    f.bars.append(Bar(1))
    f.bars.append(Bar(2))

    data = pickle(f)
    o = unpickle(data)

    assert type(o) == Foo
    assert o.name == 'foo'
    assert len(o.bars) == 2
    for i in range(2):
        assert f.bars[i].value == o.bars[i].value


def test_reentrance():
    a = {'test_ints': 42, 'test_set': set([1, 2])}
    data = pickle_obj(a)
    b = unpickle_obj(data)
    assert a == b
    other_b = unpickle_obj(data)
    assert a == other_b
    c = unpickle_obj(data)
    assert a == c

