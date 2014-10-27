import re
import os
import os.path
import fnmatch


re_terminal_path = re.compile(r'^(\w\:)?[/\\]$')


class SiteNotFoundError(Exception):
    def __init__(self, root=None, msg=None):
        if not root:
            root = os.getcwd()
        full_msg = ("No PieCrust website in '%s' "
                    "('config.yml' not found!)" %
                    root)
        if msg:
            full_msg += ": " + msg
        else:
            full_msg += "."
        Exception.__init__(self, full_msg)


def find_app_root(cwd=None):
    if cwd is None:
        cwd = os.getcwd()

    while not os.path.isfile(os.path.join(cwd, 'config.yml')):
        cwd = os.path.dirname(cwd)
        if not cwd or re_terminal_path.match(cwd):
            raise SiteNotFoundError(cwd)
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

