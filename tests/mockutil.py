import io
import time
import random
import codecs
import shutil
import os.path
import functools
import mock
import yaml
from piecrust.app import PieCrust, PieCrustConfiguration


resources_path = os.path.abspath(
            os.path.join(
            os.path.dirname(__file__),
            '..', 'piecrust', 'resources'))


def get_mock_app(config=None):
    app = mock.MagicMock(spec=PieCrust)
    app.config = PieCrustConfiguration()
    return app


def with_mock_fs_app(f):
    @functools.wraps(f)
    def wrapper(app, *args, **kwargs):
        with mock_fs_scope(app):
            real_app = app.getApp()
            return f(real_app, *args, **kwargs)
    return wrapper


class mock_fs(object):
    def __init__(self, default_spec=True):
        self._root = 'root_%d' % random.randrange(1000)
        self._fs = {self._root: {}}
        if default_spec:
            self.withDir('counter')
            self.withFile('kitchen/config.yml',
                    "site:\n  title: Mock Website\n")

    def path(self, p):
        p = p.replace('\\', '/')
        if p in ['/', '', None]:
            return '/%s' % self._root
        return '/%s/%s' % (self._root, p.lstrip('/'))

    def getApp(self):
        root_dir = self.path('/kitchen')
        return PieCrust(root_dir, cache=False)

    def withDir(self, path):
        path = path.replace('\\', '/')
        path = path.lstrip('/')
        path = '/%s/%s' % (self._root, path)
        self._createDir(path)
        return self

    def withFile(self, path, contents):
        path = path.replace('\\', '/')
        path = path.lstrip('/')
        path = '/%s/%s' % (self._root, path)
        self._createFile(path, contents)
        return self

    def withAsset(self, path, contents):
        return self.withFile('kitchen/' + path, contents)

    def withAssetDir(self, path):
        return self.withDir('kitchen/' + path)

    def withConfig(self, config):
        return self.withFile(
                'kitchen/config.yml',
                yaml.dump(config))

    def withThemeConfig(self, config):
        return self.withFile(
                'kitchen/theme/theme_config.yml',
                yaml.dump(config))

    def withPage(self, url, config=None, contents=None):
        config = config or {}
        contents = contents or "A test page."
        text = "---\n"
        text += yaml.dump(config)
        text += "---\n"
        text += contents

        name, ext = os.path.splitext(url)
        if not ext:
            url += '.md'
        url = url.lstrip('/')
        return self.withAsset(url, text)

    def withPageAsset(self, page_url, name, contents=None):
        contents = contents or "A test asset."
        url_base, ext = os.path.splitext(page_url)
        dirname = url_base + '-assets'
        return self.withAsset('%s/%s' % (dirname, name),
                contents)

    def getStructure(self, path=None):
        root = self._fs[self._root]
        if path:
            root = self._getEntry(self.path(path))

        res = {}
        for k, v in root.items():
            self._getStructureRecursive(v, res, k)
        return res

    def _getStructureRecursive(self, src, target, name):
        if isinstance(src, tuple):
            target[name] = src[0]
            return

        e = {}
        for k, v in src.items():
            self._getStructureRecursive(v, e, k)
        target[name] = e

    def _getEntry(self, path):
        cur = self._fs
        path = path.replace('\\', '/').lstrip('/')
        bits = path.split('/')
        for p in bits:
            try:
                cur = cur[p]
            except KeyError:
                return None
        return cur

    def _createDir(self, path):
        cur = self._fs
        bits = path.strip('/').split('/')
        for b in bits:
            if b not in cur:
                cur[b] = {}
            cur = cur[b]
        return self

    def _createFile(self, path, contents):
        cur = self._fs
        bits = path.strip('/').split('/')
        for b in bits[:-1]:
            if b not in cur:
                cur[b] = {}
            cur = cur[b]
        cur[bits[-1]] = (contents, {'mtime': time.time()})
        return self


class mock_fs_scope(object):
    def __init__(self, fs):
        self._fs = fs
        self._patchers = []
        self._originals = {}

    @property
    def root(self):
        return self._fs._root

    def __enter__(self):
        self._startMock()
        return self

    def __exit__(self, type, value, traceback):
        self._endMock()

    def _startMock(self):
        self._createMock('__main__.open', open, self._open, create=True)
        self._createMock('codecs.open', codecs.open, self._codecsOpen)
        self._createMock('os.listdir', os.listdir, self._listdir)
        self._createMock('os.makedirs', os.makedirs, self._makedirs)
        self._createMock('os.path.isdir', os.path.isdir, self._isdir)
        self._createMock('os.path.isfile', os.path.isfile, self._isfile)
        self._createMock('os.path.islink', os.path.islink, self._islink)
        self._createMock('os.path.getmtime', os.path.getmtime, self._getmtime)
        self._createMock('shutil.copyfile', shutil.copyfile, self._copyfile)
        for p in self._patchers:
            p.start()

    def _endMock(self):
        for p in self._patchers:
            p.stop()

    def _createMock(self, name, orig, func, **kwargs):
        self._originals[name] = orig
        self._patchers.append(mock.patch(name, func, **kwargs))

    def _open(self, path, *args, **kwargs):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['__main__.open'](path, **kwargs)
        e = self._getFsEntry(path)
        if e is None:
            raise OSError("No such file: %s" % path)
        if not isinstance(e, tuple):
            raise OSError("'%s' is not a file" % path)
        return io.StringIO(e[0])

    def _codecsOpen(self, path, *args, **kwargs):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['codecs.open'](path, *args, **kwargs)
        e = self._getFsEntry(path)
        if e is None:
            raise OSError("No such file: %s" % path)
        if not isinstance(e, tuple):
            raise OSError("'%s' is not a file" % path)
        return io.StringIO(e[0])

    def _listdir(self, path):
        if not path.startswith('/' + self.root):
            return self._originals['os.listdir'](path)
        e = self._getFsEntry(path)
        if e is None:
            raise OSError("No such directory: %s" % path)
        if not isinstance(e, dict):
            raise OSError("'%s' is not a directory." % path)
        return list(e.keys())

    def _makedirs(self, path, mode):
        if not path.startswith('/' + self.root):
            raise Exception("Shouldn't create directory: %s" % path)
        self._fs._createDir(path)

    def _isdir(self, path):
        if not path.startswith('/' + self.root):
            return self._originals['os.path.isdir'](path)
        e = self._getFsEntry(path)
        return e is not None and isinstance(e, dict)

    def _isfile(self, path):
        if not path.startswith('/' + self.root):
            return self._originals['os.path.isfile'](path)
        e = self._getFsEntry(path)
        return e is not None and isinstance(e, tuple)

    def _islink(self, path):
        if not path.startswith('/' + self.root):
            return self._originals['os.path.islink'](path)
        return False

    def _getmtime(self, path):
        if not path.startswith('/' + self.root):
            return self._originals['os.path.getmtime'](path)
        e = self._getFsEntry(path)
        if e is None:
            raise OSError("No such file: %s" % path)
        return e[1]['mtime']

    def _copyfile(self, src, dst):
        if not src.startswith('/' + self.root):
            with open(src, 'r') as fp:
                src_text = fp.read()
        else:
            e = self._getFsEntry(src)
            src_text = e[0]
        if not dst.startswith('/' + self.root):
            raise Exception("Shouldn't copy to: %s" % dst)
        self._fs._createFile(dst, src_text)

    def _getFsEntry(self, path):
        return self._fs._getEntry(path)

