import io
import sys
import time
import pprint
import os.path
import logging
import pytest
import yaml
import colorama
from werkzeug.exceptions import HTTPException
from piecrust.app import PieCrustFactory, apply_variants_and_values
from piecrust.configuration import merge_dicts
from .mockutil import mock_fs, mock_fs_scope


def pytest_runtest_setup(item):
    pass


def pytest_addoption(parser):
    parser.addoption(
        '--pc-log-debug',
        action='store_true',
        help="Sets the PieCrust logger to output debug info to stdout.")
    parser.addoption(
        '--pc-log-file',
        help="Sets the PieCrust logger to write to a file.")
    parser.addoption(
        '--pc-mock-debug',
        action='store_true',
        help="Prints contents of the mock file-system.")
    parser.addoption(
        '--pc-leave-mockfs',
        action='store_true',
        help="Leave the contents of the mock file-system on disk.")


def pytest_configure(config):
    if config.getoption('--pc-log-debug'):
        root_logger = logging.getLogger()
        hdl = logging.StreamHandler(stream=sys.stdout)
        root_logger.addHandler(hdl)
        root_logger.setLevel(logging.DEBUG)

        from .basefs import TestFileSystemBase
        TestFileSystemBase._use_chef_debug = True
        TestFileSystemBase._pytest_log_handler = hdl

    log_file = config.getoption('--pc-log-file')
    if log_file:
        hdl = logging.StreamHandler(
            stream=open(log_file, 'w', encoding='utf8'))
        logging.getLogger().addHandler(hdl)

    if config.getoption('--pc-leave-mockfs'):
        from .basefs import TestFileSystemBase
        TestFileSystemBase._leave_mockfs = True


def pytest_collect_file(parent, path):
    if path.ext == '.yaml' and path.basename.startswith("test"):
        category = os.path.basename(path.dirname)
        if category == 'bakes':
            return BakeTestFile(path, parent)
        elif category == 'cli':
            return ChefTestFile(path, parent)
        elif category == 'servings':
            return ServeTestFile(path, parent)


def repr_nested_failure(excinfo):
    # PyTest sadly doesn't show nested exceptions so we have to do it
    # ourselves... it's not pretty, but at least it's more useful.
    if excinfo.value.__cause__:
        import traceback
        ex = excinfo.value
        return '\n'.join(
            traceback.format_exception(
                type(ex), ex, ex.__traceback__))
    return ''


class YamlTestFileBase(pytest.File):
    def collect(self):
        spec = yaml.load_all(self.fspath.open(encoding='utf8'))
        for i, item in enumerate(spec):
            name = '%s_%d' % (self.fspath.basename, i)
            if 'test_name' in item:
                name += '_%s' % item['test_name']
            yield self.__item_class__(name, self, item)


class YamlTestItemBase(pytest.Item):
    def __init__(self, name, parent, spec):
        super(YamlTestItemBase, self).__init__(name, parent)
        self.spec = spec

    @property
    def is_theme_site(self):
        return self.spec.get('theme_config') is not None

    @property
    def mock_debug(self):
        return bool(self.config.getoption('--pc-mock-debug'))

    def _prepareMockFs(self):
        fs = mock_fs()

        if self.spec.get('no_kitchen', False):
            fs.withDir('/')
            return fs

        # Suppress any formatting or layout so we can compare
        # much simpler strings.
        config = {
            'site': {
                'default_format': 'none',
                'default_page_layout': 'none',
                'default_post_layout': 'none'}
        }

        # Website or theme config.
        test_theme_config = self.spec.get('theme_config')
        if test_theme_config is not None:
            merge_dicts(config, test_theme_config)
            fs.withThemeConfig(config)
        else:
            test_config = self.spec.get('config')
            if test_config is not None:
                merge_dicts(config, test_config)
            fs.withConfig(config)

        # Input file-system.
        input_files = self.spec.get('in')
        if input_files is not None:
            _add_mock_files(fs, '/kitchen', input_files)

        if self.mock_debug:
            res = '\nMock File-System:\n'
            res += 'At: %s\n' % fs.path('')
            res += '\n'.join(print_fs_tree(fs.path('')))
            res += '\n'
            print(res)

        return fs

    def repr_failure(self, excinfo):
        res = super(YamlTestItemBase, self).repr_failure(excinfo)
        nested_res = repr_nested_failure(excinfo)
        if nested_res:
            res = str(res) + '\n' + nested_res
        return res


def check_expected_outputs(spec, fs, error_type):
    cctx = CompareContext()
    expected_output_files = spec.get('out')
    if expected_output_files:
        actual = fs.getStructure('kitchen/_counter')
        error = _compare_dicts(expected_output_files, actual, cctx)
        if error:
            raise error_type(error)

    expected_partial_files = spec.get('outfiles')
    if expected_partial_files:
        keys = list(sorted(expected_partial_files.keys()))
        for key in keys:
            try:
                actual = fs.getFileEntry('kitchen/_counter/' +
                                         key.lstrip('/'))
            except Exception as e:
                lines = print_fs_tree(fs.path('kitchen/_counter'))
                raise error_type([
                    "Can't access output file %s: %s" % (key, e),
                    "Got output directory:"] +
                    lines)

            expected = expected_partial_files[key]
            # HACK because for some reason PyYAML adds a new line for
            # those and I have no idea why.
            actual = actual.rstrip('\n')
            expected = expected.rstrip('\n')
            cctx.path = key
            cmpres = _compare_str(expected, actual, cctx)
            if cmpres:
                raise error_type(cmpres)


def print_fs_tree(rootpath):
    import os
    import os.path
    lines = []
    offset = len(rootpath)
    for pathname, dirnames, filenames in os.walk(rootpath):
        level = pathname[offset:].count(os.sep)
        indent = ' ' * 4 * (level)
        lines.append(indent + os.path.basename(pathname) + '/')
        indent2 = ' ' * 4 * (level + 1)
        for f in filenames:
            lines.append(indent2 + f)
    return lines


class ChefTestItem(YamlTestItemBase):
    __initialized_logging__ = False

    def runtest(self):
        if not ChefTestItem.__initialized_logging__:
            colorama.init()
            hdl = logging.StreamHandler(stream=sys.stdout)
            logging.getLogger().addHandler(hdl)
            logging.getLogger().setLevel(logging.INFO)
            ChefTestItem.__initialized_logging__ = True

        fs = self._prepareMockFs()

        argv = self.spec['args']
        if isinstance(argv, str):
            argv = argv.split(' ')
        if self.is_theme_site:
            argv.insert(0, '--theme')
        if not self.spec.get('no_kitchen', False):
            argv = ['--root', fs.path('/kitchen')] + argv

        with mock_fs_scope(fs, keep=self.mock_debug):
            cwd = os.getcwd()
            memstream = io.StringIO()
            hdl = logging.StreamHandler(stream=memstream)
            logging.getLogger().addHandler(hdl)
            try:
                from piecrust.main import _pre_parse_chef_args, _run_chef
                os.chdir(fs.path('/'))
                pre_args = _pre_parse_chef_args(argv)
                exit_code = _run_chef(pre_args, argv)
            finally:
                logging.getLogger().removeHandler(hdl)
                os.chdir(cwd)

            expected_code = self.spec.get('code', 0)
            if expected_code != exit_code:
                raise UnexpectedChefExitCodeError("Got '%d', expected '%d'." %
                                                  (exit_code, expected_code))

            expected_out = self.spec.get('out', None)
            if expected_out is not None:
                actual_out = memstream.getvalue()
                if not self.spec.get('no_strip'):
                    actual_out = actual_out.rstrip(' \n')
                    expected_out = expected_out.rstrip(' \n')
                if self.spec.get('replace_out_path_sep'):
                    expected_out = expected_out.replace('/', os.sep)
                if expected_out != actual_out:
                    raise UnexpectedChefOutputError(expected_out, actual_out)

            expected_files = self.spec.get('files', None)
            if expected_files is not None:
                for path in expected_files:
                    path = '/' + path.lstrip('/')
                    if not os.path.exists(fs.path(path)):
                        raise MissingChefOutputFileError(fs, path)

    def reportinfo(self):
        return self.fspath, 0, "bake: %s" % self.name

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, UnexpectedChefExitCodeError):
            return str(excinfo.value)
        if isinstance(excinfo.value, UnexpectedChefOutputError):
            return ('\n'.join(
                ['Unexpected command output. Expected:',
                 excinfo.value.args[0],
                 "Got:",
                 excinfo.value.args[1]]))
        if isinstance(excinfo.value, MissingChefOutputFileError):
            lines = print_fs_tree(excinfo.value.args[0].path(''))
            return ('\n'.join(
                ["Missing file: %s" % excinfo.value.args[1],
                 "Got output directory:"] +
                lines))
        return super(ChefTestItem, self).repr_failure(excinfo)


class UnexpectedChefExitCodeError(Exception):
    pass


class UnexpectedChefOutputError(Exception):
    pass


class MissingChefOutputFileError(Exception):
    pass


class ChefTestFile(YamlTestFileBase):
    __item_class__ = ChefTestItem


class BakeTestItem(YamlTestItemBase):
    def runtest(self):
        fs = self._prepareMockFs()

        from piecrust.baking.baker import Baker
        with mock_fs_scope(fs, keep=self.mock_debug):
            out_dir = fs.path('kitchen/_counter')
            app = fs.getApp(theme_site=self.is_theme_site)

            values = self.spec.get('config_values')
            if values is not None:
                values = list(values.items())
            variants = self.spec.get('config_variants')
            apply_variants_and_values(app, variants, values)

            appfactory = PieCrustFactory(app.root_dir,
                                         theme_site=self.is_theme_site,
                                         config_variants=variants,
                                         config_values=values)
            baker = Baker(appfactory, app, out_dir)
            records = baker.bake()

            if not records.success:
                errors = []
                for r in records.records:
                    for e in r.getEntries():
                        errors += e.getAllErrors()
                raise BakeError(errors)

            check_expected_outputs(self.spec, fs, UnexpectedBakeOutputError)

    def reportinfo(self):
        return self.fspath, 0, "bake: %s" % self.name

    def repr_failure(self, excinfo):
        if isinstance(excinfo.value, UnexpectedBakeOutputError):
            return ('\n'.join(
                ['Unexpected bake output. Left is expected output, '
                    'right is actual output'] +
                excinfo.value.args[0]))
        elif isinstance(excinfo.value, BakeError):
            res = ('\n'.join(
                ['Errors occured during bake:'] +
                excinfo.value.args[0]))
            res += repr_nested_failure(excinfo)
            return res
        return super(BakeTestItem, self).repr_failure(excinfo)


class BakeError(Exception):
    pass


class UnexpectedBakeOutputError(Exception):
    pass


class BakeTestFile(YamlTestFileBase):
    __item_class__ = BakeTestItem


class ServeTestItem(YamlTestItemBase):
    def runtest(self):
        fs = self._prepareMockFs()

        url = self.spec.get('url')
        if url is None:
            raise Exception("Missing URL in test spec.")

        expected_status = self.spec.get('status', 200)
        expected_headers = self.spec.get('headers')
        expected_output = self.spec.get('out')
        expected_contains = self.spec.get('out_contains')

        from werkzeug.test import Client
        from werkzeug.wrappers import BaseResponse
        from piecrust.app import PieCrustFactory
        from piecrust.serving.server import PieCrustServer

        with mock_fs_scope(fs, keep=self.mock_debug):
            appfactory = PieCrustFactory(
                fs.path('/kitchen'),
                theme_site=self.is_theme_site)
            server = PieCrustServer(appfactory)

            client = Client(server, BaseResponse)
            resp = client.get(url)
            if expected_status != resp.status_code:
                raise UnexpectedChefServingError(
                    url,
                    "Expected HTTP status '%s', got '%s'" %
                    (expected_status, resp.status_code),
                    resp)

            if expected_headers:
                for k, v in expected_headers.items():
                    assert v == resp.headers.get(k)

            actual = resp.data.decode('utf8').rstrip()
            if expected_output:
                assert expected_output.rstrip() == actual

            if expected_contains:
                assert expected_contains.rstrip() in actual

    def reportinfo(self):
        return self.fspath, 0, "serve: %s" % self.name

    def repr_failure(self, excinfo):
        from piecrust.serving.server import MultipleNotFound
        if isinstance(excinfo.value, MultipleNotFound):
            res = '\n'.join(
                ["HTTP error 404 returned:",
                 str(excinfo.value)] +
                [str(e) for e in excinfo.value._nfes])
            res += repr_nested_failure(excinfo)
            return res
        elif isinstance(excinfo.value, HTTPException):
            res = '\n'.join(
                ["HTTP error %s returned:" % excinfo.value.code,
                 excinfo.value.description])
            res += repr_nested_failure(excinfo)
            return res
        elif isinstance(excinfo.value, UnexpectedChefServingError):
            res = str(excinfo.value)
            res += '\nWhile requesting URL: %s' % excinfo.value.url
            res += '\nBody:\n%s' % excinfo.value.resp.data.decode('utf8')
            return res
        return super(ServeTestItem, self).repr_failure(excinfo)


class UnexpectedChefServingError(Exception):
    def __init__(self, url, msg, resp):
        super().__init__(msg)
        self.url = url
        self.resp = resp


class ServeTestFile(YamlTestFileBase):
    __item_class__ = ServeTestItem


def _add_mock_files(fs, parent_path, spec):
    for name, subspec in spec.items():
        path = os.path.join(parent_path, name)
        if isinstance(subspec, str):
            fs.withFile(path, subspec)
        elif isinstance(subspec, dict):
            _add_mock_files(fs, path, subspec)


class CompareContext(object):
    def __init__(self, path=None, t=None):
        self.path = path or ''
        self.time = t or time.time()

    def createChildContext(self, name):
        ctx = CompareContext(
            path='%s/%s' % (self.path, name),
            t=self.time)
        return ctx


def _compare(left, right, ctx):
    if type(left) != type(right):
        return (["Different items: ",
                 "%s: %s" % (ctx.path, pprint.pformat(left)),
                 "%s: %s" % (ctx.path, pprint.pformat(right))])
    if isinstance(left, str):
        return _compare_str(left, right, ctx)
    elif isinstance(left, dict):
        return _compare_dicts(left, right, ctx)
    elif isinstance(left, list):
        return _compare_lists(left, right, ctx)
    elif left != right:
        return (["Different items: ",
                 "%s: %s" % (ctx.path, pprint.pformat(left)),
                 "%s: %s" % (ctx.path, pprint.pformat(right))])


def _compare_dicts(left, right, ctx):
    key_diff = set(left.keys()) ^ set(right.keys())
    if key_diff:
        extra_left = set(left.keys()) - set(right.keys())
        if extra_left:
            return (["Left contains more items: "] +
                    ['- %s/%s' % (ctx.path, k) for k in extra_left] +
                    ['Left:', ', '.join(left.keys())] +
                    ['Right:', ', '.join(right.keys())])
        extra_right = set(right.keys()) - set(left.keys())
        if extra_right:
            return (["Right contains more items: "] +
                    ['- %s/%s' % (ctx.path, k) for k in extra_right] +
                    ['Left:', ', '.join(left.keys())] +
                    ['Right:', ', '.join(right.keys())])
        return ["Unknown difference"]

    for key in left.keys():
        lv = left[key]
        rv = right[key]
        child_ctx = ctx.createChildContext(key)
        cmpres = _compare(lv, rv, child_ctx)
        if cmpres:
            return cmpres
    return None


def _compare_lists(left, right, ctx):
    for i in range(min(len(left), len(right))):
        lc = left[i]
        rc = right[i]
        cmpres = _compare(lc, rc, ctx)
        if cmpres:
            return cmpres
    if len(left) > len(right):
        return (["Left '%s' contains more items. First extra item: " %
                 ctx.path, left[len(right)]])
    if len(right) > len(left):
        return (["Right '%s' contains more items. First extra item: " %
                 ctx.path, right[len(left)]])
    return None


def _compare_str(left, right, ctx):
    if left == right:
        return None

    test_time_iso8601 = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                      time.gmtime(ctx.time))
    test_time_iso8601_pattern = '%test_time_iso8601%'

    left_time_indices = []
    i = -1
    while True:
        i = left.find(test_time_iso8601_pattern, i + 1)
        if i >= 0:
            left_time_indices.append(i)
            left = (left[:i] + test_time_iso8601 +
                    left[i + len(test_time_iso8601_pattern):])
        else:
            break

    skip_for = -1
    for i in range(min(len(left), len(right))):
        if skip_for > 0:
            skip_for -= 1
            continue

        if i in left_time_indices:
            # This is where the time starts. Let's compare that the time
            # values are within a few seconds of each other (usually 0 or 1).
            right_time_str = right[i:i + len(test_time_iso8601)]
            right_time = time.strptime(right_time_str, '%Y-%m-%dT%H:%M:%SZ')
            left_time = time.gmtime(ctx.time)
            # Need to patch the daylist-savings-time flag because it can
            # mess up the computation of the time difference.
            right_time = (right_time[0], right_time[1], right_time[2],
                          right_time[3], right_time[4], right_time[5],
                          right_time[6], right_time[7],
                          left_time.tm_isdst)
            difference = time.mktime(left_time) - time.mktime(right_time)
            print("Got time difference: %d" % difference)
            if abs(difference) <= 1:
                print("(good enough, moving to end of timestamp)")
                skip_for = len(test_time_iso8601) - 1

        if left[i] != right[i]:
            start = max(0, i - 15)
            l_end = min(len(left), i + 15)
            r_end = min(len(right), i + 15)

            l_str = ''
            l_offset = 0
            for j in range(start, l_end):
                c = repr(left[j]).strip("'")
                l_str += c
                if j < i:
                    l_offset += len(c)

            r_str = ''
            r_offset = 0
            for j in range(start, r_end):
                c = repr(right[j]).strip("'")
                r_str += c
                if j < i:
                    r_offset += len(c)

            return ["Items '%s' differ at index %d:" % (ctx.path, i), '',
                    "Left:", left, '',
                    "Right:", right, '',
                    "Difference:",
                    l_str, (' ' * l_offset + '^'),
                    r_str, (' ' * r_offset + '^')]

    if len(left) > len(right):
        return ["Left is longer.",
                "Left '%s': " % ctx.path, left,
                "Right '%s': " % ctx.path, right,
                "Extra items: %r" % left[len(right):]]

    if len(right) > len(left):
        return ["Right is longer.",
                "Left '%s': " % ctx.path, left,
                "Right '%s': " % ctx.path, right,
                "Extra items: %r" % right[len(left):]]

