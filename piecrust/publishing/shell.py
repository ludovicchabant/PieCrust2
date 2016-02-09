import shlex
from piecrust.publishing.base import ShellCommandPublisherBase


class ShellCommandPublisher(ShellCommandPublisherBase):
    PUBLISHER_NAME = 'shell'

    def _getCommandArgs(self, ctx):
        target_cmd = self.getConfigValue('cmd')
        if not target_cmd:
            raise Exception("No command specified for publish target: %s" %
                            self.target)
        args = shlex.split(target_cmd)
        return args

