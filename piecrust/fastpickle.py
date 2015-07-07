import sys
import datetime
import collections


def pickle(obj):
    return _pickle_object(obj)


def unpickle(data):
    return _unpickle_object(data)


def _tuple_dispatch(obj, func):
    res = [None] * len(obj)
    for i, c in enumerate(obj):
        res[i] = func(c)
    return tuple(res)


def _list_dispatch(obj, func):
    res = [None] * len(obj)
    for i, c in enumerate(obj):
        res[i] = func(c)
    return res


def _dict_dispatch(obj, func):
    res = {}
    for k, v in obj.items():
        res[k] = func(v)
    return res


def _set_dispatch(obj, func):
    res = set()
    for v in obj:
        res.add(func(v))
    return res


_identity_dispatch = object()

_type_dispatch = {
        type(None): _identity_dispatch,
        bool: _identity_dispatch,
        int: _identity_dispatch,
        float: _identity_dispatch,
        str: _identity_dispatch,
        datetime.date: _identity_dispatch,
        datetime.datetime: _identity_dispatch,
        datetime.time: _identity_dispatch,
        tuple: _tuple_dispatch,
        list: _list_dispatch,
        dict: _dict_dispatch,
        collections.OrderedDict: _dict_dispatch,
        set: _set_dispatch
        }


def _pickle_object(obj):
    t = type(obj)
    disp = _type_dispatch.get(t)
    if disp is _identity_dispatch:
        return obj

    if disp is not None:
        return disp(obj, _pickle_object)

    if isinstance(obj, Exception):
        return obj

    getter = getattr(obj, '__getstate__', None)
    if getter is not None:
        state = getter()
    else:
        state = obj.__dict__

    state = _dict_dispatch(state, _pickle_object)
    state['__class__'] = obj.__class__.__name__
    state['__module__'] = obj.__class__.__module__

    return state


def _unpickle_object(state):
    t = type(state)
    disp = _type_dispatch.get(t)
    if disp is _identity_dispatch:
        return state

    if (disp is not None and
            (t != dict or '__module__' not in state)):
        return disp(state, _unpickle_object)

    if isinstance(state, Exception):
        return state

    mod_name = state['__module__']
    mod = sys.modules[mod_name]
    class_name = state['__class__']
    class_def = getattr(mod, class_name)
    obj = class_def.__new__(class_def)

    del state['__class__']
    del state['__module__']
    attr_names = list(state.keys())
    for name in attr_names:
        state[name] = _unpickle_object(state[name])

    obj.__dict__.update(state)

    return obj

