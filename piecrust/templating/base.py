

class TemplateNotFoundError(Exception):
    pass


class TemplatingError(Exception):
    def __init__(self, message, filename=None, lineno=-1):
        super(TemplatingError, self).__init__()
        self.message = message
        self.filename = filename
        self.lineno = lineno

    def __str__(self):
        msg = ''
        if self.filename:
            msg += self.filename
        if self.lineno >= 0:
            msg += ', line %d' % self.lineno
        msg += ': ' + self.message
        return msg


class TemplateEngine(object):
    EXTENSIONS = []

    def initialize(self, app):
        self.app = app

    def populateCache(self):
        pass

    def renderSegment(self, path, segment, data):
        raise NotImplementedError()

    def renderFile(self, paths, data):
        raise NotImplementedError()
