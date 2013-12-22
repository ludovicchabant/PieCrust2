import logging
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class RootCommand(ChefCommand):
    def __init__(self):
        super(RootCommand, self).__init__()
        self.name = 'root'
        self.description = "Gets the root directory of the current website."

    def setupParser(self, parser):
        pass

    def run(self, ctx):
        logger.info(ctx.app.root)

