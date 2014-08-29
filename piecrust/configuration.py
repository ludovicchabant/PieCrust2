import re
import logging
import collections
import yaml
from yaml.constructor import ConstructorError


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    pass


class Configuration(object):
    def __init__(self, values=None, validate=True):
        if values is not None:
            self.setAll(values, validate)
        else:
            self._values = None

    def setAll(self, values, validate=True):
        if validate:
            self._validateAll(values)
        self._values = values

    def getAll(self):
        return self.get()

    def get(self, key_path=None):
        self._ensureLoaded()
        if key_path is None:
            return self._values
        bits = key_path.split('/')
        cur = self._values
        for b in bits:
            cur = cur.get(b)
            if cur is None:
                return None
        return cur

    def set(self, key_path, value):
        self._ensureLoaded()
        value = self._validateValue(key_path, value)
        bits = key_path.split('/')
        bitslen = len(bits)
        cur = self._values
        for i, b in enumerate(bits):
            if i == bitslen - 1:
                cur[b] = value
            else:
                if b not in cur:
                    cur[b] = {}
                cur = cur[b]

    def has(self, key_path):
        self._ensureLoaded()
        bits = key_path.split('/')
        cur = self._values
        for b in bits:
            cur = cur.get(b)
            if cur is None:
                return False
        return True

    def merge(self, other):
        self._ensureLoaded()
        merge_dicts(self._values, other._values,
                validator=self._validateValue)

    def _ensureLoaded(self):
        if self._values is None:
            self._load()

    def _load(self):
        self._values = self._validateAll({})

    def _validateAll(self, values):
        return values

    def _validateValue(self, key_path, value):
        return value


def merge_dicts(source, merging, validator=None, *args):
    if validator is None:
        validator = lambda k, v: v
    _recurse_merge_dicts(source, merging, None, validator)
    for other in args:
        _recurse_merge_dicts(source, other, None, validator)


def _recurse_merge_dicts(local_cur, incoming_cur, parent_path, validator):
    for k, v in incoming_cur.items():
        key_path = k
        if parent_path is not None:
            key_path = parent_path + '/' + k

        local_v = local_cur.get(k)
        if local_v is not None:
            if isinstance(v, dict) and isinstance(local_v, dict):
                _recurse_merge_dicts(local_v, v, key_path, validator)
            elif isinstance(v, list) and isinstance(local_v, list):
                local_cur[k] = v + local_v
            else:
                local_cur[k] = validator(key_path, v)
        else:
            local_cur[k] = validator(key_path, v)


header_regex = re.compile(
        r'(---\s*\n)(?P<header>(.*\n)*?)^(---\s*\n)', re.MULTILINE)


def parse_config_header(text):
    m = header_regex.match(text)
    if m is not None:
        header = str(m.group('header'))
        config = yaml.load(header, Loader=OrderedDictYAMLLoader)
        offset = m.end()
    else:
        config = {}
        offset = 0
    return config, offset


class OrderedDictYAMLLoader(yaml.BaseLoader):
    """ A YAML loader that loads mappings into ordered dictionaries.
    """
    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise ConstructorError(None, None,
                    "expected a mapping node, but found %s" % node.id,
                    node.start_mark)
        mapping = collections.OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, collections.Hashable):
                raise ConstructorError("while constructing a mapping", node.start_mark,
                        "found unhashable key", key_node.start_mark)
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping

