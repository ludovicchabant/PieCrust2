

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
        author = author or self.config.get('author')
        self._doCommit(paths, message, author)

    def _doCommit(self, paths, message, author):
        raise NotImplementedError()

