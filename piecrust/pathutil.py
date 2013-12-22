import os
import os.path


class SiteNotFoundError(Exception):
    def __init__(self, root=None):
        if not root:
            root = os.getcwd()
        Exception.__init__(self,
                "No PieCrust website in '%s' "
                "('_content/config.yml' not found!)." % root)


def find_app_root(cwd=None):
    if cwd is None:
        cwd = os.getcwd()

    while not os.path.isfile(os.path.join(cwd, '_content', 'config.yml')):
        cwd = os.path.dirname(cwd)
        if not cwd or cwd == '/':
            return None
    return cwd

