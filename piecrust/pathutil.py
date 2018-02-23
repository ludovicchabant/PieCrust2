import re
import os
import os.path
import fnmatch
from piecrust import CONFIG_PATH, THEME_CONFIG_PATH


re_terminal_path = re.compile(r'^(\w\:)?[/\\]$')


class SiteNotFoundError(Exception):
    def __init__(self, root=None, msg=None, theme=False):
        if not root:
            root = os.getcwd()

        cfg_name = CONFIG_PATH
        if theme:
            cfg_name = THEME_CONFIG_PATH

        full_msg = ("No PieCrust website in '%s' "
                    "('%s' not found!)" % (root, cfg_name))
        if msg:
            full_msg += ": " + msg
        else:
            full_msg += "."
        Exception.__init__(self, full_msg)


def find_app_root(cwd=None, theme=False):
    if cwd is None:
        cwd = os.getcwd()

    cfg_name = CONFIG_PATH
    if theme:
        cfg_name = THEME_CONFIG_PATH

    while not os.path.isfile(os.path.join(cwd, cfg_name)):
        cwd = os.path.dirname(cwd)
        if not cwd or re_terminal_path.match(cwd):
            raise SiteNotFoundError(cwd, theme=theme)
    return cwd


def multi_fnmatch_filter(names, patterns, modifier=None, inverse=True):
    res = []
    for n in names:
        matches = False
        test_n = modifier(n) if modifier else n
        for p in patterns:
            if fnmatch.fnmatch(test_n, p):
                matches = True
                break
        if matches and not inverse:
            res.append(n)
        elif not matches and inverse:
            res.append(n)
    return res


def ensure_dir(path, mode=0o755):
    try:
        os.makedirs(path, mode=mode, exist_ok=True)
    except OSError:
        pass
