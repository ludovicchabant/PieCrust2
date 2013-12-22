from piecrust.commands.builtin.info import RootCommand
from piecrust.commands.builtin.util import InitCommand
from piecrust.plugins.base import PieCrustPlugin


class BuiltInPlugin(PieCrustPlugin):
    def __init__(self):
        super(BuiltInPlugin, self).__init__()
        self.name = '__builtin__'

    def getCommands(self):
        return [
                InitCommand(),
                RootCommand()]

