import os
import sys
import glob as _system_glob
import unicodedata


walk = os.walk
listdir = os.listdir
glob = _system_glob.glob


def _wrap_fs_funcs():
    global walk
    global listdir
    global glob

    def _walk(top, **kwargs):
        for dirpath, dirnames, filenames in os.walk(top, **kwargs):
            dirpath = _from_osx_fs(dirpath)
            dirnames[:] = list(map(_from_osx_fs, dirnames))
            filenames[:] = list(map(_from_osx_fs, filenames))
            yield dirpath, dirnames, filenames

    def _listdir(path='.'):
        for name in os.listdir(path):
            name = _from_osx_fs(name)
            yield name

    def _glob(pathname):
        pathname = _to_osx_fs(pathname)
        matches = _system_glob.glob(pathname)
        return list(map(_from_osx_fs, matches))

    def _from_osx_fs(s):
        return unicodedata.normalize('NFC', s)

    def _to_osx_fs(s):
        return unicodedata.ucd_3_2_0.normalize('NFD', s)

    walk = _walk
    listdir = _listdir
    glob = _glob


_do_wrap_mac_fs = False

if _do_wrap_mac_fs and sys.platform == 'darwin':
    _wrap_fs_funcs()

