import logging


logger = logging.getLogger(__name__)


class CommandContext(object):
    def __init__(self, args, app):
        self.args = args
        self.app = app


class ChefCommand(object):
    def __init__(self):
        self.name = '__unknown__'
        self.description = '__unknown__'
        self.requires_website = True

    def setupParser(self, parser):
        raise NotImplementedError()

    def run(self, ctx):
        raise NotImplementedError()


class RootCommand(ChefCommand):
    def __init__(self):
        super(RootCommand, self).__init__()
        self.name = 'root'
        self.description = "Gets the root directory of the current website."

    def setupParser(self, parser):
        pass

    def run(self, ctx):
        logger.info(ctx.app.root)

