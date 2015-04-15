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
            error = _compare_dicts(actual, expected_output_files)
            if error:
                raise ExpectedBakeOutputError(error)

        if expected_partial_files:
            for key, content in expected_partial_files.items():
                try:
                    actual = fs.getStructure('kitchen/_counter/' +
                                             key.lstrip('/'))
                except Exception:
                    raise ExpectedBakeOutputError([
                        "Missing expected output file: %s" % key])
                if not isinstance(actual, str):
                    raise ExpectedBakeOutputError([
                        "Expected output file is a directory: %s" % key])
                if actual != content:
                    raise ExpectedBakeOutputError([
                        "Unexpected output file contents:",
                        "%s: %s" % (key, content),
                        "%s: %s" % (key, actual)])

    def reportinfo(self):
        return self.fspath, 0, "bake: %s" % self.name

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, ExpectedBakeOutputError):
            return ('\n'.join(excinfo.value.args[0]))
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
        if type(lv) != type(rv):
            return (["Different items: ",
                     "%s/%s: %s" % (basepath, key, pprint.pformat(lv)),
                     "%s/%s: %s" % (basepath, key, pprint.pformat(rv))])

        if isinstance(lv, dict):
            r = _compare_dicts(lv, rv, childpath)
            if r:
                return r
        elif isinstance(lv, list):
            r = _compare_lists(lv, rv, childpath)
            if r:
                return r
        elif lv != rv:
            return (["Different items: ",
                     "%s/%s: %s" % (basepath, key, pprint.pformat(lv)),
                     "%s/%s: %s" % (basepath, key, pprint.pformat(rv))])
    return None


def _compare_lists(left, right):
    for i in range(min(len(left), len(right))):
        l = left[i]
        r = right[i]
        if type(l) != type(r):
            return ['Different items at index %d:' % i,
                    pprint.pformat(l),
                    pprint.pformat(r)]
        if isinstance(l, dict):
            r = _compare_dicts(l, r)
            if r:
                return r
        elif isinstance(l, list):
            r = _compare_lists(l, r)
            if r:
                return r
        elif l != r:
            return ['Different items at index %d:' % i,
                    pprint.pformat(l),
                    pprint.pformat(r)]
    return None

