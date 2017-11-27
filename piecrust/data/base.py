import time
import collections.abc


class MergedMapping(collections.abc.Mapping):
    """ Provides a dictionary-like object that's really the aggregation of
        multiple dictionary-like objects.
    """
    def __init__(self, dicts, path=''):
        self._dicts = dicts
        self._path = path

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError("No such attribute: %s" % self._subp(name))

    def __getitem__(self, name):
        values = []
        for d in self._dicts:
            try:
                val = getattr(d, name)
                values.append(val)
                continue
            except AttributeError:
                pass

            try:
                val = d[name]
                values.append(val)
                continue
            except KeyError:
                pass

        if len(values) == 0:
            raise KeyError("No such item: %s" % self._subp(name))
        if len(values) == 1:
            return values[0]

        for val in values:
            if not isinstance(val, (dict, collections.abc.Mapping)):
                raise Exception(
                    "Template data for '%s' contains an incompatible mix "
                    "of data: %s" % (
                        self._subp(name),
                        ', '.join([str(type(v)) for v in values])))

        return MergedMapping(values, self._subp(name))

    def __iter__(self):
        keys = set()
        for d in self._dicts:
            keys |= set(d.keys())
        return iter(keys)

    def __len__(self):
        keys = set()
        for d in self._dicts:
            keys |= set(d.keys())
        return len(keys)

    def _subp(self, name):
        return '%s/%s' % (self._path, name)

    def _prependMapping(self, d):
        self._dicts.insert(0, d)

    def _appendMapping(self, d):
        self._dicts.append(d)

