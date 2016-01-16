

class RepoStatus(object):
    def __init__(self):
        self.new_files = []
        self.edited_files = []


class SourceControl(object):
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def getStatus(self):
        raise NotImplementedError()

    def commit(self, paths, author, message):
        raise NotImplementedError()

