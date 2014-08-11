

class TemplateNotFoundError(Exception):
    pass


class TemplateEngine(object):
    EXTENSIONS = []

    def initialize(self, app):
        self.app = app

    def renderString(self, txt, data, filename=None, line_offset=0):
        raise NotImplementedError()

    def renderFile(self, paths, data):
        raise NotImplementedError()
