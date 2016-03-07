import os.path
import io
import time
import errno
import random
import codecs
import shutil
import mock
from piecrust import RESOURCES_DIR
from .basefs import TestFileSystemBase


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


class MemoryFileSystem(TestFileSystemBase):
    def __init__(self):
        self._root = 'root_%d' % random.randrange(1000)
        self._fs = {self._root: {}}

    def path(self, p):
        p = p.replace('\\', '/')
        if p in ['/', '', None]:
            return '/%s' % self._root
        return '/%s/%s' % (self._root, p.lstrip('/'))

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


class MemoryScope(object):
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
        modules = self.open_patches + [
                '__main__',
                'piecrust.records',
                'jinja2.utils']
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
        if path.startswith(RESOURCES_DIR):
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
                err = IOError("File '%s' already exists" % path)
                err.errno = errno.EEXIST
                raise err
        else:
            err = IOError("Unsupported open mode: %s" % mode)
            err.errno = errno.EINVAL
            raise err

        if e is None:
            err = IOError("No such file: %s" % path)
            err.errno = errno.ENOENT
            raise err
        if not isinstance(e, _MockFsEntry):
            err = IOError("'%s' is not a file %s" % (path, e))
            err.errno = errno.EISDIR
            raise err

        return _MockFsEntryWriter(e, mode)

    def _open(self, path, mode, *args, **kwargs):
        return self._doOpen('__main__.open', path, mode, *args, **kwargs)

    def _codecsOpen(self, path, mode, *args, **kwargs):
        return self._doOpen('codecs.open', path, mode, *args, **kwargs)

    def _listdir(self, path):
        path = os.path.normpath(path)
        if path.startswith(RESOURCES_DIR):
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
        if path.startswith(RESOURCES_DIR):
            return self._originals['os.path.isdir'](path)
        e = self._getFsEntry(path)
        return e is not None

    def _isdir(self, path):
        path = os.path.normpath(path)
        if path.startswith(RESOURCES_DIR):
            return self._originals['os.path.isdir'](path)
        e = self._getFsEntry(path)
        return e is not None and isinstance(e, dict)

    def _isfile(self, path):
        path = os.path.normpath(path)
        if path.startswith(RESOURCES_DIR):
            return self._originals['os.path.isfile'](path)
        e = self._getFsEntry(path)
        return e is not None and isinstance(e, _MockFsEntry)

    def _islink(self, path):
        path = os.path.normpath(path)
        if path.startswith(RESOURCES_DIR):
            return self._originals['os.path.islink'](path)
        return False

    def _getmtime(self, path):
        path = os.path.normpath(path)
        if path.startswith(RESOURCES_DIR):
            return self._originals['os.path.getmtime'](path)
        e = self._getFsEntry(path)
        if e is None:
            raise OSError("No such file: %s" % path)
        return e.metadata['mtime']

    def _copyfile(self, src, dst):
        src = os.path.normpath(src)
        if src.startswith(RESOURCES_DIR):
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
        if src.startswith(RESOURCES_DIR) or dst.startswith(RESOURCES_DIR):
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

