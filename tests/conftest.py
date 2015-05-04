import sys
import pprint
import os.path
import logging
import pytest
import yaml
from piecrust.configuration import merge_dicts
from .mockutil import mock_fs, mock_fs_scope


def pytest_runtest_setup(item):
    pass


def pytest_addoption(parser):
    parser.addoption(
            '--log-debug',
            action='store_true',
            help="Sets the PieCrust logger to output debug info to stdout.")


def pytest_configure(config):
    if config.getoption('--log-debug'):
        hdl = logging.StreamHandler(stream=sys.stdout)
        logging.getLogger('piecrust').addHandler(hdl)
        logging.getLogger('piecrust').setLevel(logging.DEBUG)


def pytest_collect_file(parent, path):
    if path.ext == ".bake" and path.basename.startswith("test"):
        return BakeTestFile(path, parent)


class BakeTestFile(pytest.File):
    def collect(self):
        spec = yaml.load_all(self.fspath.open())
        for i, item in enumerate(spec):
            name = '%s_%d' % (self.fspath.basename, i)
            if 'test_name' in item:
                name += '_%s' % item['test_name']
            yield BakeTestItem(name, self, item)


class BakeTestItem(pytest.Item):
    def __init__(self, name, parent, spec):
        super(BakeTestItem, self).__init__(name, parent)
        self.spec = spec

    def runtest(self):
        fs = mock_fs()

        # Website config.
        config = {
                'site': {
                    'default_format': 'none',
                    'default_page_layout': 'none',
                    'default_post_layout': 'none'}
                }
        test_config = self.spec.get('config')
        if test_config is not None:
            merge_dicts(config, test_config)
        fs.withConfig(config)

        # Input file-system.
        input_files = self.spec.get('in')
        if input_files is not None:
            _add_mock_files(fs, '/kitchen', input_files)

        # Output file-system.
        expected_output_files = self.spec.get('out')
        expected_partial_files = self.spec.get('outfiles')

        # Bake!
        from piecrust.baking.baker import Baker
        with mock_fs_scope(fs):
            out_dir = fs.path('kitchen/_counter')
            app = fs.getApp()
            baker = Baker(app, out_dir)
            baker.bake()

        if expected_output_files:
            actual = fs.getStructure('kitchen/_counter')
            error = _compare_dicts(expected_output_files, actual)
            if error:
                raise ExpectedBakeOutputError(error)

        if expected_partial_files:
            keys = list(sorted(expected_partial_files.keys()))
            for key in keys:
                try:
                    actual = fs.getFileEntry('kitchen/_counter/' +
                                             key.lstrip('/'))
                except Exception as e:
                    raise ExpectedBakeOutputError([
                        "Can't access output file %s: %s" % (key, e)])

                expected = expected_partial_files[key]
                # HACK because for some reason PyYAML adds a new line for those
                # and I have no idea why.
                actual = actual.rstrip('\n')
                expected = expected.rstrip('\n')
                cmpres = _compare_str(expected, actual, key)
                if cmpres:
                    raise ExpectedBakeOutputError(cmpres)

    def reportinfo(self):
        return self.fspath, 0, "bake: %s" % self.name

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, ExpectedBakeOutputError):
            return ('\n'.join(
                ['Unexpected bake output. Left is expected output, '
                    'right is actual output'] +
                excinfo.value.args[0]))
        return super(BakeTestItem, self).repr_failure(excinfo)


class ExpectedBakeOutputError(Exception):
    pass


def _add_mock_files(fs, parent_path, spec):
    for name, subspec in spec.items():
        path = os.path.join(parent_path, name)
        if isinstance(subspec, str):
            fs.withFile(path, subspec)
        elif isinstance(subspec, dict):
            _add_mock_files(fs, path, subspec)


def _compare(left, right, path):
    if type(left) != type(right):
        return (["Different items: ",
                 "%s: %s" % (path, pprint.pformat(left)),
                 "%s: %s" % (path, pprint.pformat(right))])
    if isinstance(left, str):
        return _compare_str(left, right, path)
    elif isinstance(left, dict):
        return _compare_dicts(left, right, path)
    elif isinstance(left, list):
        return _compare_lists(left, right, path)
    elif left != right:
        return (["Different items: ",
                 "%s: %s" % (path, pprint.pformat(left)),
                 "%s: %s" % (path, pprint.pformat(right))])


def _compare_dicts(left, right, basepath=''):
    key_diff = set(left.keys()) ^ set(right.keys())
    if key_diff:
        extra_left = set(left.keys()) - set(right.keys())
        if extra_left:
            return (["Left contains more items: "] +
                    ['- %s/%s' % (basepath, k) for k in extra_left])
        extra_right = set(right.keys()) - set(left.keys())
        if extra_right:
            return (["Right contains more items: "] +
                    ['- %s/%s' % (basepath, k) for k in extra_right])
        return ["Unknown difference"]

    for key in left.keys():
        lv = left[key]
        rv = right[key]
        childpath = basepath + '/' + key
        cmpres = _compare(lv, rv, childpath)
        if cmpres:
            return cmpres
    return None


def _compare_lists(left, right, path):
    for i in range(min(len(left), len(right))):
        l = left[i]
        r = right[i]
        cmpres = _compare(l, r, path)
        if cmpres:
            return cmpres
    if len(left) > len(right):
        return (["Left '%s' contains more items. First extra item: " % path,
                 left[len(right)]])
    if len(right) > len(left):
        return (["Right '%s' contains more items. First extra item: " % path,
                 right[len(left)]])
    return None


def _compare_str(left, right, path):
    if left == right:
        return None
    for i in range(min(len(left), len(right))):
        if left[i] != right[i]:
            start = max(0, i - 15)
            marker_offset = min(15, (i - start)) + 3

            lend = min(len(left), i + 15)
            rend = min(len(right), i + 15)

            return ["Items '%s' differ at index %d:" % (path, i), '',
                    "Left:", left, '',
                    "Right:", right, '',
                    "Difference:",
                    repr(left[start:lend]),
                    (' ' * marker_offset + '^'),
                    repr(right[start:rend]),
                    (' ' * marker_offset + '^')]
    if len(left) > len(right):
        return ["Left is longer.",
                "Left '%s': " % path, left,
                "Right '%s': " % path, right,
                "Extra items: %r" % left[len(right):]]
    if len(right) > len(left):
        return ["Right is longer.",
                "Left '%s': " % path, left,
                "Right '%s': " % path, right,
                "Extra items: %r" % right[len(left):]]

