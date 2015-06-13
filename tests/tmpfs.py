import os
import os.path
import shutil
import random
from .basefs import TestFileSystemBase


class TempDirFileSystem(TestFileSystemBase):
    def __init__(self, default_spec=True):
        self._root = os.path.join(
                os.path.dirname(__file__),
                '__tmpfs__',
                '%d' % random.randrange(1000))
        self._done = False
        if default_spec:
            self._initDefaultSpec()

    def path(self, p):
        p = p.lstrip('/\\')
        return os.path.join(self._root, p)

    def getStructure(self, path=None):
        path = self.path(path)
        if not os.path.exists(path):
            raise Exception("No such path: %s" % path)
        if not os.path.isdir(path):
            raise Exception("Path is not a directory: %s" % path)

        res = {}
        for item in os.listdir(path):
            self._getStructureRecursive(res, path, item)
        return res

    def getFileEntry(self, path):
        path = self.path(path)
        with open(path, 'r', encoding='utf8') as fp:
            return fp.read()

    def _getStructureRecursive(self, target, parent, cur):
        full_cur = os.path.join(parent, cur)
        if os.path.isdir(full_cur):
            e = {}
            for item in os.listdir(full_cur):
                self._getStructureRecursive(e, full_cur, item)
            target[cur] = e
        else:
            with open(full_cur, 'r', encoding='utf8') as fp:
                target[cur] = fp.read()

    def _createDir(self, path):
        if not os.path.exists(path):
            os.makedirs(path)

    def _createFile(self, path, contents):
        dirpath = os.path.dirname(path)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        with open(path, 'w', encoding='utf8') as fp:
            fp.write(contents)

        if not self._done:
            import traceback
            with open(os.path.join(self._root, 'where.txt'), 'w') as fp:
                fp.write('\n'.join(traceback.format_stack(limit=10)))
            self._done = True


class TempDirScope(object):
    def __init__(self, fs, open_patches=None):
        self._fs = fs
        self._open = open

    @property
    def root(self):
        return self._fs._root

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        shutil.rmtree(self.root)

