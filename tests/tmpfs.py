import os
import os.path
import shutil
import random
import unicodedata
from .basefs import TestFileSystemBase


class TempDirFileSystem(TestFileSystemBase):
    def __init__(self):
        self._root = os.path.join(
            os.path.dirname(__file__),
            '__tmpfs__',
            '%d' % random.randrange(1000))
        self._done = False

    def path(self, p):
        p = p.lstrip('/\\')
        return os.path.join(self._root, p)

    def getStructure(self, path=''):
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
        cur = unicodedata.normalize('NFC', cur)
        full_cur = os.path.join(parent, cur)
        if os.path.isdir(full_cur):
            e = {}
            for item in os.listdir(full_cur):
                self._getStructureRecursive(e, full_cur, item)
            target[cur] = e
        else:
            try:
                with open(full_cur, 'r', encoding='utf8') as fp:
                    target[cur] = fp.read()
            except Exception as ex:
                target[cur] = "ERROR: CAN'T READ '%s': %s" % (full_cur, ex)

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
    def __init__(self, fs, open_patches=None, keep=False):
        self._fs = fs
        self._open = open
        self._keep = keep or TestFileSystemBase._leave_mockfs

    @property
    def root(self):
        return self._fs._root

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if not self._keep:
            shutil.rmtree(self.root)

