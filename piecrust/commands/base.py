import logging
from piecrust.pathutil import SiteNotFoundError


logger = logging.getLogger(__name__)


class CommandContext(object):
    def __init__(self, app, args):
        self.app = app
        self.args = args


class ChefCommand(object):
    def __init__(self):
        self.name = '__unknown__'
        self.description = '__unknown__'
        self.requires_website = True

    def setupParser(self, parser):
        raise NotImplementedError()

    def run(self, ctx):
        raise NotImplementedError()

    def _runFromChef(self, app, res):
        if app.root is None and self.requires_website:
            raise SiteNotFoundError()
        self.run(CommandContext(app, res))

