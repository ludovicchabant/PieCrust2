from piecrust.publishing.shell import ShellCommandPublisherBase


class RsyncPublisher(ShellCommandPublisherBase):
    PUBLISHER_NAME = 'rsync'
    PUBLISHER_SCHEME = 'rsync'

    def parseUrlTarget(self, url):
        self.config = {
            'destination': (url.netloc + url.path)
        }

    def _getCommandArgs(self, ctx):
        orig = self.config.get('source', ctx.bake_out_dir)
        dest = self.config.get('destination')
        if not dest:
            raise Exception("No destination specified.")

        rsync_options = self.config.get('options')
        if rsync_options is None:
            rsync_options = ['-avc', '--delete']

        args = ['rsync'] + rsync_options
        args += [orig, dest]
        return args

