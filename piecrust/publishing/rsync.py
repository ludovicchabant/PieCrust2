from piecrust.publishing.base import ShellCommandPublisherBase


class RsyncPublisher(ShellCommandPublisherBase):
    PUBLISHER_NAME = 'rsync'
    PUBLISHER_SCHEME = 'rsync'

    def _getCommandArgs(self, ctx):
        if self.has_url_config:
            orig = ctx.bake_out_dir
            dest = self.parsed_url.netloc + self.parsed_url.path
        else:
            orig = self.getConfigValue('source', ctx.bake_our_dir)
            dest = self.getConfigValue('destination')

        rsync_options = None
        if not self.has_url_config:
            rsync_options = self.getConfigValue('options')
        if rsync_options is None:
            rsync_options = ['-avc', '--delete']

        args = ['rsync'] + rsync_options
        args += [orig, dest]
        return args

