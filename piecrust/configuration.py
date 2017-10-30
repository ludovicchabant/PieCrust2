import re
import logging
import collections
import collections.abc
import yaml
from yaml.constructor import ConstructorError
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


logger = logging.getLogger(__name__)

default_allowed_types = (dict, list, tuple, float, int, bool, str)


MERGE_NEW_VALUES = 0
MERGE_OVERWRITE_VALUES = 1
MERGE_PREPEND_LISTS = 2
MERGE_APPEND_LISTS = 4
MERGE_ALL = MERGE_OVERWRITE_VALUES | MERGE_PREPEND_LISTS


class ConfigurationError(Exception):
    pass


class Configuration(collections.abc.MutableMapping):
    def __init__(self, values=None, validate=True):
        if values is not None:
            self.setAll(values, validate=validate)
        else:
            self._values = None

    def __getitem__(self, key):
        self._ensureLoaded()
        try:
            return get_dict_value(self._values, key)
        except KeyError:
            raise KeyError("No such item: %s" % key)

    def __setitem__(self, key, value):
        self._ensureLoaded()
        value = self._validateValue(key, value)
        set_dict_value(self._values, key, value)

    def __delitem__(self, key):
        raise NotImplementedError()

    def __iter__(self):
        self._ensureLoaded()
        return iter(self._values)

    def __len__(self):
        self._ensureLoaded()
        return len(self._values)

    def has(self, key):
        return key in self

    def set(self, key, value):
        self[key] = value

    def setAll(self, values, validate=False):
        if validate:
            values = self._validateAll(values)
        self._values = values

    def getAll(self):
        self._ensureLoaded()
        return self._values

    def merge(self, other, mode=MERGE_ALL):
        self._ensureLoaded()

        if isinstance(other, dict):
            other_values = other
        elif isinstance(other, Configuration):
            other_values = other._values
        else:
            raise Exception(
                "Unsupported value type to merge: %s" % type(other))

        merge_dicts(self._values, other_values,
                    mode=mode,
                    validator=self._validateValue)

    def validateTypes(self, allowed_types=default_allowed_types):
        self._validateDictTypesRecursive(self._values, allowed_types)

    def _validateDictTypesRecursive(self, d, allowed_types):
        for k, v in d.items():
            if not isinstance(k, str):
                raise ConfigurationError("Key '%s' is not a string." % k)
            self._validateTypeRecursive(v, allowed_types)

    def _validateListTypesRecursive(self, l, allowed_types):
        for v in l:
            self._validateTypeRecursive(v, allowed_types)

    def _validateTypeRecursive(self, v, allowed_types):
        if v is None:
            return
        if not isinstance(v, allowed_types):
            raise ConfigurationError(
                "Value '%s' is of forbidden type: %s" % (v, type(v)))
        if isinstance(v, dict):
            self._validateDictTypesRecursive(v, allowed_types)
        elif isinstance(v, list):
            self._validateListTypesRecursive(v, allowed_types)

    def _ensureLoaded(self):
        if self._values is None:
            self._load()

    def _load(self):
        self._values = self._validateAll({})

    def _validateAll(self, values):
        return values

    def _validateValue(self, key_path, value):
        return value


def get_dict_value(d, key):
    bits = key.split('/')
    cur = d
    for b in bits:
        cur = cur[b]
    return cur


def get_dict_values(*args):
    for d, key in args:
        try:
            return get_dict_value(d, key)
        except KeyError:
            continue
    raise KeyError()


def try_get_dict_value(d, key, *, default=None):
    try:
        return get_dict_value(d, key)
    except KeyError:
        return default


def try_get_dict_values(*args, default=None):
    for d, key in args:
        try:
            return get_dict_value(d, key)
        except KeyError:
            continue
    return default


def set_dict_value(d, key, value):
    bits = key.split('/')
    bitslen = len(bits)
    cur = d
    for i, b in enumerate(bits):
        if i == bitslen - 1:
            cur[b] = value
        else:
            if b not in cur:
                cur[b] = {}
            cur = cur[b]


def merge_dicts(source, merging, *args,
                validator=None, mode=MERGE_ALL):
    _recurse_merge_dicts(source, merging, None, validator, mode)
    for other in args:
        _recurse_merge_dicts(source, other, None, validator, mode)
    return source


def _recurse_merge_dicts(local_cur, incoming_cur, parent_path,
                         validator, mode):
    for k, v in incoming_cur.items():
        key_path = k
        if parent_path is not None:
            key_path = parent_path + '/' + k

        local_v = local_cur.get(k)
        if local_v is not None:
            if isinstance(v, dict) and isinstance(local_v, dict):
                _recurse_merge_dicts(local_v, v, key_path,
                                     validator, mode)
            elif isinstance(v, list) and isinstance(local_v, list):
                if mode & MERGE_PREPEND_LISTS:
                    local_cur[k] = v + local_v
                elif mode & MERGE_APPEND_LISTS:
                    local_cur[k] = local_v + v
            else:
                if mode & MERGE_OVERWRITE_VALUES:
                    if validator is not None:
                        v = validator(key_path, v)
                    local_cur[k] = v
        else:
            if ((mode & (MERGE_PREPEND_LISTS | MERGE_APPEND_LISTS)) or
                    not isinstance(v, list)):
                if validator is not None:
                    v = validator(key_path, v)
                local_cur[k] = v


def visit_dict(subject, visitor):
    _recurse_visit_dict(subject, None, visitor)


def _recurse_visit_dict(cur, parent_path, visitor):
    for k, v in cur.items():
        key_path = k
        if parent_path is not None:
            key_path = parent_path + '/' + k

        visitor(key_path, v, cur, k)
        if isinstance(v, dict):
            _recurse_visit_dict(v, key_path, visitor)


header_regex = re.compile(
    r'(---\s*\n)(?P<header>(.*\n)*?)^(---\s*\n)', re.MULTILINE)


def parse_config_header(text):
    m = header_regex.match(text)
    if m is not None:
        header = str(m.group('header'))
        config = yaml.load(header, Loader=ConfigurationLoader)
        offset = m.end()
    else:
        config = {}
        offset = 0
    return config, offset


class ConfigurationLoader(SafeLoader):
    """ A YAML loader that loads mappings into ordered dictionaries,
        and supports sexagesimal notations for timestamps.
    """
    def __init__(self, *args, **kwargs):
        super(ConfigurationLoader, self).__init__(*args, **kwargs)

        self.add_constructor('tag:yaml.org,2002:map',
                             type(self).construct_yaml_map)
        self.add_constructor('tag:yaml.org,2002:omap',
                             type(self).construct_yaml_map)
        self.add_constructor('tag:yaml.org,2002:sexagesimal',
                             type(self).construct_yaml_time)

    def construct_yaml_map(self, node):
        data = collections.OrderedDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise ConstructorError(
                None, None,
                "expected a mapping node, but found %s" % node.id,
                node.start_mark)
        mapping = collections.OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, collections.Hashable):
                raise ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    "found unhashable key", key_node.start_mark)
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping

    time_regexp = re.compile(
        r'''^(?P<hour>[0-9][0-9]?)
                :(?P<minute>[0-9][0-9])
                (:(?P<second>[0-9][0-9])
                (\.(?P<fraction>[0-9]+))?)?$''', re.X)

    def construct_yaml_time(self, node):
        self.construct_scalar(node)
        match = self.time_regexp.match(node.value)
        values = match.groupdict()
        hour = int(values['hour'])
        minute = int(values['minute'])
        second = 0
        if values['second']:
            second = int(values['second'])
        usec = 0
        if values['fraction']:
            usec = float('0.' + values['fraction'])
        return second + minute * 60 + hour * 60 * 60 + usec


ConfigurationLoader.add_implicit_resolver(
    'tag:yaml.org,2002:sexagesimal',
    re.compile(r'''^[0-9][0-9]?:[0-9][0-9]
                    (:[0-9][0-9](\.[0-9]+)?)?$''', re.X),
    list('0123456789'))


# We need to add our `sexagesimal` resolver before the `int` one, which
# already supports sexagesimal notation in YAML 1.1 (but not 1.2). However,
# because we know we pretty much always want it for representing time, we
# need a simple `12:30` to mean 45000, not 750. So that's why we override
# the default behaviour.
for ch in list('0123456789'):
    ch_resolvers = ConfigurationLoader.yaml_implicit_resolvers[ch]
    ch_resolvers.insert(0, ch_resolvers.pop())


class ConfigurationDumper(yaml.SafeDumper):
    def represent_ordered_dict(self, data):
        # Not a typo: we're using `map` and not `omap` because we don't want
        # ugly type tags printed in the generated YAML markup, and because
        # we always load maps into `OrderedDicts` anyway.
        return self.represent_mapping('tag:yaml.org,2002:map', data)


ConfigurationDumper.add_representer(collections.OrderedDict,
                                    ConfigurationDumper.represent_ordered_dict)

