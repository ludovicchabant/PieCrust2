import functools


def lazy(f):
    @functools.wraps(f)
    def lazy_wrapper(*args, **kwargs):
        if f.__lazyresult__ is None:
            f.__lazyresult__ = f(*args, **kwargs)
        return f.__lazyresult__

    f.__lazyresult__ = None
    return lazy_wrapper


def lazy_property(f):
    return property(lazy(f))

