import copy
import yaml
import pytest
from collections import OrderedDict
from piecrust.configuration import (
    Configuration, ConfigurationLoader, merge_dicts,
    MERGE_APPEND_LISTS, MERGE_PREPEND_LISTS, MERGE_OVERWRITE_VALUES)


@pytest.mark.parametrize('values, expected', [
    (None, {}),
    ({'foo': 'bar'}, {'foo': 'bar'})
])
def test_config_init(values, expected):
    config = Configuration(values)
    assert config.getAll() == expected


def test_config_set_all():
    config = Configuration()
    config.setAll({'foo': 'bar'})
    assert config.getAll() == {'foo': 'bar'}


def test_config_get_and_set():
    config = Configuration({'foo': 'bar', 'answer': 42})
    assert config.get('foo') == 'bar'
    assert config.get('answer') == 42

    config.set('foo', 'something')
    assert config.get('foo') == 'something'


def test_config_get_and_set_nested():
    config = Configuration({
        'foo': [4, 2],
        'bar': {
            'child1': 'one',
            'child2': 'two'
        }
    })
    assert config.get('foo') == [4, 2]
    assert config.get('bar/child1') == 'one'
    assert config.get('bar/child2') == 'two'

    config.set('bar/child1', 'other one')
    config.set('bar/child3', 'new one')
    assert config.get('bar/child1') == 'other one'
    assert config.get('bar/child3') == 'new one'


def test_config_get_missing():
    config = Configuration({'foo': 'bar'})
    assert config.get('baz') is None


def test_config_has():
    config = Configuration({'foo': 'bar'})
    assert config.has('foo') is True
    assert config.has('baz') is False


def test_config_deep_set_non_existing():
    config = Configuration({'foo': 'bar'})
    assert config.get('baz') is None
    config.set('baz/or/whatever', 'something')
    assert config.has('baz') is True
    assert config.has('baz/or') is True
    assert config.get('baz/or/whatever') == 'something'


def test_config_deep_set_existing():
    config = Configuration({'foo': 'bar', 'baz': {'wat': 'nothing'}})
    assert config.has('baz') is True
    assert config.get('baz/wat') == 'nothing'
    assert config.get('baz/or') is None
    config.set('baz/or/whatever', 'something')
    assert config.has('baz') is True
    assert config.has('baz/or') is True
    assert config.get('baz/or/whatever') == 'something'


@pytest.mark.parametrize('local, incoming, expected', [
    ({}, {}, {}),
    ({'foo': 'bar'}, {}, {'foo': 'bar'}),
    ({}, {'foo': 'bar'}, {'foo': 'bar'}),
    ({'foo': 'bar'}, {'foo': 'other'}, {'foo': 'other'}),
    ({'foo': [1, 2]}, {'foo': [3]}, {'foo': [3, 1, 2]}),
    ({'foo': [1, 2]}, {'foo': 'bar'}, {'foo': 'bar'}),
    ({'foo': {'bar': 1, 'baz': 2}}, {'foo': 'bar'}, {'foo': 'bar'}),
    ({'foo': {'bar': 1, 'baz': 2}}, {'foo': {'other': 3}},
     {'foo': {'bar': 1, 'baz': 2, 'other': 3}}),
    ({'foo': {'bar': 1, 'baz': 2}}, {'foo': {'baz': 10}},
     {'foo': {'bar': 1, 'baz': 10}})
])
def test_merge_dicts(local, incoming, expected):
    local2 = copy.deepcopy(local)
    merge_dicts(local2, incoming)
    assert local2 == expected


def test_config_merge():
    config = Configuration({
        'foo': [4, 2],
        'bar': {
            'child1': 'one',
            'child2': 'two'
        }
    })
    other = Configuration({
        'baz': True,
        'blah': 'blah blah',
        'bar': {
            'child1': 'other one',
            'child10': 'ten'
        }
    })
    config.merge(other)

    expected = {
        'foo': [4, 2],
        'baz': True,
        'blah': 'blah blah',
        'bar': {
            'child1': 'other one',
            'child2': 'two',
            'child10': 'ten'
        }
    }
    assert config.getAll() == expected


@pytest.mark.parametrize('mode, expected', [
    (MERGE_APPEND_LISTS,
     {'foo': [4, 2, 1, 0], 'bar': 'something'}),
    (MERGE_PREPEND_LISTS,
     {'foo': [1, 0, 4, 2], 'bar': 'something'}),
    (MERGE_OVERWRITE_VALUES,
     {'foo': [4, 2], 'bar': 'other thing'})
])
def test_config_merge_with_mode(mode, expected):
    config = Configuration({
        'foo': [4, 2],
        'bar': 'something'
    })
    other = {'foo': [1, 0], 'bar': 'other thing'}
    config.merge(other, mode=mode)
    assert config.getAll() == expected


def test_ordered_loader():
    sample = """
one:
    two: fish
    red: fish
    blue: fish
two:
    a: yes
    b: no
    c: null
"""
    data = yaml.load(sample, Loader=ConfigurationLoader)
    assert type(data) is OrderedDict
    assert list(data['one'].keys()) == ['two', 'red', 'blue']


def test_load_time1():
    sample = """
time: 21:35
"""
    data = yaml.load(sample, Loader=ConfigurationLoader)
    assert type(data['time']) is int
    assert data['time'] == (21 * 60 * 60 + 35 * 60)


def test_load_time2():
    sample = """
time: 21:35:50
"""
    data = yaml.load(sample, Loader=ConfigurationLoader)
    assert type(data['time']) is int
    assert data['time'] == (21 * 60 * 60 + 35 * 60 + 50)

