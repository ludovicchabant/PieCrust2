

class RepoStatus(object):
    def __init__(self):
        self.new_files = []
        self.edited_files = []


class SourceControl(object):
    def __init__(self, root_dir, cfg):
        self.root_dir = root_dir
        self.config = cfg

    def getStatus(self):
        raise NotImplementedError()

    def commit(self, paths, message, *, author=None):
        if not message:
            raise ValueError("No message specified for committing changes.")
        author = author or self.config.get('author')
        self._doCommit(paths, message, author)

    def _doCommit(self, paths, message, author):
        raise NotImplementedError()


def _s(strs):
    """ Convert a byte array to string using UTF8 encoding. """
    if strs is None:
        return None
    assert isinstance(strs, bytes)
    return strs.decode('utf8')

