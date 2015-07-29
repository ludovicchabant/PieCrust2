import os
import sys
import glob as _glob
import unicodedata


if sys.platform == 'darwin':
    def walk(top, **kwargs):
        for dirpath, dirnames, filenames in os.walk(top, **kwargs):
            dirpath = _from_osx_fs(dirpath)
            dirnames = list(map(_from_osx_fs, dirnames))
            filenames = list(map(_from_osx_fs, filenames))
            yield dirpath, dirnames, filenames

    def listdir(path='.'):
        for name in os.listdir(path):
            name = _from_osx_fs(name)
            yield name

    def glob(pathname):
        pathname = _to_osx_fs(pathname)
        matches = _glob.glob(pathname)
        return list(map(_from_osx_fs, matches))

    def _from_osx_fs(s):
        return unicodedata.normalize('NFC', s)

    def _to_osx_fs(s):
        return unicodedata.ucd_3_2_0.normalize('NFD', s)

else:
    walk = sys.walk
    listdir = sys.listdir
    glob = _glob.glob

