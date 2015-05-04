import io
import time
import random
import codecs
import shutil
import os.path
import mock
import yaml
from piecrust.app import PieCrust, PieCrustConfiguration
from piecrust.page import Page
from piecrust.rendering import QualifiedPage, PageRenderingContext, render_page


resources_path = os.path.abspath(
            os.path.join(
            os.path.dirname(__file__),
            '..', 'piecrust', 'resources'))


def get_mock_app(config=None):
    app = mock.MagicMock(spec=PieCrust)
    app.config = PieCrustConfiguration()
    return app


def get_simple_page(app, rel_path):
    source = app.getSource('pages')
    metadata = {'slug': os.path.splitext(rel_path)[0]}
    return Page(source, metadata, rel_path)


def render_simple_page(page, route, route_metadata):
    qp = QualifiedPage(page, route, route_metadata)
    ctx = PageRenderingContext(qp)
    rp = render_page(ctx)
    return rp.content


class _MockFsEntry(object):
    def __init__(self, contents):
        self.contents = contents
        self.metadata = {'mtime': time.time()}


class _MockFsEntryWriter(object):
    def __init__(self, entry, mode='rt'):
        self._entry = entry
        self._mode = mode

        if 'b' in mode:
            data = entry.contents
            if isinstance(data, str):
                data = data.encode('utf8')
            self._stream = io.BytesIO(data)
        else:
            self._stream = io.StringIO(entry.contents)

    def __getattr__(self, name):
        return getattr(self._stream, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if 'w' in self._mode:
            if 'a' in self._mode:
                self._entry.contents += self._stream.getvalue()
            else:
                self._entry.contents = self._stream.getvalue()
            self._entry.metadata['mtime'] = time.time()
        self._stream.close()


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

    def getApp(self, cache=True):
        root_dir = self.path('/kitchen')
        return PieCrust(root_dir, cache=cache, debug=True)

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

    def withPages(self, num, url_factory, config_factory=None,
                  contents_factory=None):
        for i in range(num):
            if isinstance(url_factory, str):
                url = url_factory.format(idx=i, idx1=(i + 1))
            else:
                url = url_factory(i)

            config = None
            if config_factory:
                config = config_factory(i)

            contents = None
            if contents_factory:
                contents = contents_factory(i)

            self.withPage(url, config, contents)
        return self

    def getStructure(self, path=None):
        root = self._fs[self._root]
        if path:
            root = self._getEntry(self.path(path))
            if root is None:
                raise Exception("No such path: %s" % path)
            if not isinstance(root, dict):
                raise Exception("Path is not a directory: %s" % path)

        res = {}
        for k, v in root.items():
            self._getStructureRecursive(v, res, k)
        return res

    def getFileEntry(self, path):
        entry = self._getEntry(self.path(path))
        if entry is None:
            raise Exception("No such file: %s" % path)
        if not isinstance(entry, _MockFsEntry):
            raise Exception("Path is not a file: %s" % path)
        return entry.contents

    def _getStructureRecursive(self, src, target, name):
        if isinstance(src, _MockFsEntry):
            target[name] = src.contents
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
        path = path.replace('\\', '/').strip('/')
        bits = path.split('/')
        for b in bits:
            if b not in cur:
                cur[b] = {}
            cur = cur[b]
        return self

    def _createFile(self, path, contents):
        cur = self._fs
        path = path.replace('\\', '/').lstrip('/')
        bits = path.split('/')
        for b in bits[:-1]:
            if b not in cur:
                cur[b] = {}
            cur = cur[b]
        cur[bits[-1]] = _MockFsEntry(contents)
        return self

    def _deleteEntry(self, path):
        parent = self._getEntry(os.path.dirname(path))
        assert parent is not None
        name = os.path.basename(path)
        assert name in parent
        del parent[name]


class mock_fs_scope(object):
    def __init__(self, fs, open_patches=None):
        self.open_patches = open_patches or []
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
        # TODO: sadly, there seems to be no way to replace `open` everywhere?
        modules = self.open_patches + ['__main__', 'piecrust.records']
        for m in modules:
            self._createMock('%s.open' % m, open, self._open, create=True)

        self._createMock('codecs.open', codecs.open, self._codecsOpen)
        self._createMock('os.listdir', os.listdir, self._listdir)
        self._createMock('os.makedirs', os.makedirs, self._makedirs)
        self._createMock('os.remove', os.remove, self._remove)
        self._createMock('os.rename', os.rename, self._rename)
        self._createMock('os.path.exists', os.path.exists, self._exists)
        self._createMock('os.path.isdir', os.path.isdir, self._isdir)
        self._createMock('os.path.isfile', os.path.isfile, self._isfile)
        self._createMock('os.path.islink', os.path.islink, self._islink)
        self._createMock('os.path.getmtime', os.path.getmtime, self._getmtime)
        self._createMock('shutil.copyfile', shutil.copyfile, self._copyfile)
        self._createMock('shutil.rmtree', shutil.rmtree, self._rmtree)
        for p in self._patchers:
            p.start()

    def _endMock(self):
        for p in self._patchers:
            p.stop()

    def _createMock(self, name, orig, func, **kwargs):
        self._originals[name] = orig
        self._patchers.append(mock.patch(name, func, **kwargs))

    def _doOpen(self, orig_name, path, mode, *args, **kwargs):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals[orig_name](path, mode, *args, **kwargs)

        if 'r' in mode:
            e = self._getFsEntry(path)
        elif 'w' in mode or 'x' in mode or 'a' in mode:
            e = self._getFsEntry(path)
            if e is None:
                contents = ''
                if 'b' in mode:
                    contents = bytes()
                self._fs._createFile(path, contents)
                e = self._getFsEntry(path)
                assert e is not None
            elif 'x' in mode:
                raise OSError("File '%s' already exists" % path)
        else:
            raise OSError("Unsupported open mode: %s" % mode)

        if e is None:
            raise OSError("No such file: %s" % path)
        if not isinstance(e, _MockFsEntry):
            raise OSError("'%s' is not a file %s" % (path, e))

        return _MockFsEntryWriter(e, mode)

    def _open(self, path, mode, *args, **kwargs):
        return self._doOpen('__main__.open', path, mode, *args, **kwargs)

    def _codecsOpen(self, path, mode, *args, **kwargs):
        return self._doOpen('codecs.open', path, mode, *args, **kwargs)

    def _listdir(self, path):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['os.listdir'](path)

        e = self._getFsEntry(path)
        if e is None:
            raise OSError("No such directory: %s" % path)
        if not isinstance(e, dict):
            raise OSError("'%s' is not a directory." % path)
        return list(e.keys())

    def _makedirs(self, path, mode=0o777):
        if not path.replace('\\', '/').startswith('/' + self.root):
            raise Exception("Shouldn't create directory: %s" % path)
        self._fs._createDir(path)

    def _remove(self, path):
        path = os.path.normpath(path)
        self._fs._deleteEntry(path)

    def _exists(self, path):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['os.path.isdir'](path)
        e = self._getFsEntry(path)
        return e is not None

    def _isdir(self, path):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['os.path.isdir'](path)
        e = self._getFsEntry(path)
        return e is not None and isinstance(e, dict)

    def _isfile(self, path):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['os.path.isfile'](path)
        e = self._getFsEntry(path)
        return e is not None and isinstance(e, _MockFsEntry)

    def _islink(self, path):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['os.path.islink'](path)
        return False

    def _getmtime(self, path):
        path = os.path.normpath(path)
        if path.startswith(resources_path):
            return self._originals['os.path.getmtime'](path)
        e = self._getFsEntry(path)
        if e is None:
            raise OSError("No such file: %s" % path)
        return e.metadata['mtime']

    def _copyfile(self, src, dst):
        src = os.path.normpath(src)
        if src.startswith(resources_path):
            with self._originals['__main__.open'](src, 'r') as fp:
                src_text = fp.read()
        else:
            e = self._getFsEntry(src)
            src_text = e.contents
        if not dst.replace('\\', '/').startswith('/' + self.root):
            raise Exception("Shouldn't copy to: %s" % dst)
        self._fs._createFile(dst, src_text)

    def _rename(self, src, dst):
        src = os.path.normpath(src)
        if src.startswith(resources_path) or dst.startswith(resources_path):
            raise Exception("Shouldn't rename files in the resources path.")
        self._copyfile(src, dst)
        self._remove(src)

    def _rmtree(self, path):
        if not path.replace('\\', '/').startswith('/' + self.root):
            raise Exception("Shouldn't delete trees from: %s" % path)
        e = self._fs._getEntry(os.path.dirname(path))
        del e[os.path.basename(path)]

    def _getFsEntry(self, path):
        return self._fs._getEntry(path)

