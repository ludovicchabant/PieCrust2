import re
import os
import os.path


re_terminal_path = re.compile(r'[/\\]|(\w\:)')


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

