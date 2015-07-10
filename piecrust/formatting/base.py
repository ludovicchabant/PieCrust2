
PRIORITY_FIRST = -1
PRIORITY_NORMAL = 0
PRIORITY_LAST = 1


class Formatter(object):
    FORMAT_NAMES = None
    OUTPUT_FORMAT = None

    def __init__(self):
        self.priority = PRIORITY_NORMAL
        self.enabled = True

    def initialize(self, app):
        self.app = app

    def render(self, format_name, txt):
        raise NotImplementedError()

