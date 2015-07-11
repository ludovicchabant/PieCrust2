import sys
import datetime
import collections


def pickle(obj):
    return _pickle_object(obj)


def unpickle(data):
    return _unpickle_object(data)


_PICKLING = 0
_UNPICKLING = 1


def _tuple_dispatch(obj, func, op):
    res = [None] * len(obj)
    for i, c in enumerate(obj):
        res[i] = func(c)
    return tuple(res)


def _list_dispatch(obj, func, op):
    res = [None] * len(obj)
    for i, c in enumerate(obj):
        res[i] = func(c)
    return res


def _dict_dispatch(obj, func, op):
    res = {}
    for k, v in obj.items():
        res[k] = func(v)
    return res


def _set_dispatch(obj, func, op):
    res = set()
    for v in obj:
        res.add(func(v))
    return res


def _date_convert(obj, op):
    if op == _PICKLING:
        return {'__class__': 'date',
                'year': obj.year,
                'month': obj.month,
                'day': obj.day}
    elif op == _UNPICKLING:
        return datetime.date(
                obj['year'], obj['month'], obj['day'])


def _datetime_convert(obj, op):
    if op == _PICKLING:
        return {'__class__': 'datetime',
                'year': obj.year,
                'month': obj.month,
                'day': obj.day,
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond}
    elif op == _UNPICKLING:
        return datetime.datetime(
                obj['year'], obj['month'], obj['day'],
                obj['hour'], obj['minute'], obj['second'], obj['microsecond'])


def _time_convert(obj, op):
    if op == _PICKLING:
        return {'__class__': 'time',
                'hour': obj.hour,
                'minute': obj.minute,
                'second': obj.second,
                'microsecond': obj.microsecond}
    elif op == _UNPICKLING:
        return datetime.time(
                obj['hour'], obj['minute'], obj['second'], obj['microsecond'])


_identity_dispatch = object()

_type_dispatch = {
        type(None): _identity_dispatch,
        bool: _identity_dispatch,
        int: _identity_dispatch,
        float: _identity_dispatch,
        str: _identity_dispatch,
        tuple: _tuple_dispatch,
        list: _list_dispatch,
        dict: _dict_dispatch,
        collections.OrderedDict: _dict_dispatch,
        set: _set_dispatch
        }


_type_convert = {
        datetime.date: _date_convert,
        datetime.datetime: _datetime_convert,
        datetime.time: _time_convert
        }


_type_unconvert = {
        'date': _date_convert,
        'datetime': _datetime_convert,
        'time': _time_convert
        }


def _pickle_object(obj):
    t = type(obj)
    disp = _type_dispatch.get(t)
    if disp is _identity_dispatch:
        return obj

    if disp is not None:
        return disp(obj, _pickle_object, _PICKLING)

    conv = _type_convert.get(t)
    if conv is not None:
        return conv(obj, _PICKLING)

    getter = getattr(obj, '__getstate__', None)
    if getter is not None:
        state = getter()
    else:
        state = obj.__dict__

    state = _dict_dispatch(state, _pickle_object, _PICKLING)
    state['__class__'] = obj.__class__.__name__
    state['__module__'] = obj.__class__.__module__

    return state


def _unpickle_object(state):
    t = type(state)
    disp = _type_dispatch.get(t)
    if disp is _identity_dispatch:
        return state

    if (disp is not None and
            (t != dict or '__class__' not in state)):
        return disp(state, _unpickle_object, _UNPICKLING)

    class_name = state['__class__']
    conv = _type_unconvert.get(class_name)
    if conv is not None:
        return conv(state, _UNPICKLING)

    mod_name = state['__module__']
    mod = sys.modules[mod_name]
    class_def = getattr(mod, class_name)
    obj = class_def.__new__(class_def)

    del state['__class__']
    del state['__module__']
    attr_names = list(state.keys())
    for name in attr_names:
        state[name] = _unpickle_object(state[name])

    obj.__dict__.update(state)

    return obj

