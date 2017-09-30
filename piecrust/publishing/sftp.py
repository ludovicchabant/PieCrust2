import os
import os.path
import logging
from piecrust.publishing.base import Publisher, PublisherConfigurationError


logger = logging.getLogger(__name__)


class SftpPublisher(Publisher):
    PUBLISHER_NAME = 'sftp'
    PUBLISHER_SCHEME = 'sftp'

    def setupPublishParser(self, parser, app):
        parser.add_argument(
            '--force',
            action='store_true',
            help=("Upload the entire bake directory instead of only "
                  "the files changed by the last bake."))

    def parseUrlTarget(self, url):
        self.config = {'host': str(url)}

    def run(self, ctx):
        host = self.config.get('host')
        if not host:
            raise PublisherConfigurationError(
                "Publish target '%s' doesn't specify a 'host'." %
                self.target)

        import urllib.parse
        remote = urllib.parse.urlparse(host)

        hostname = remote.hostname
        port = remote.port or 22
        path = remote.path
        if not hostname:
            hostname = path
            path = ''

        username = self.config.get('username', remote.username)
        path = self.config.get('path', path)
        pkey_path = self.config.get('key')

        password = None
        if username and not ctx.preview:
            import getpass
            password = getpass.getpass("Password for '%s': " % username)

        if ctx.preview:
            logger.info("Would connect to %s:%s..." % (hostname, port))
            self._previewUpload(ctx, path)
            return

        import paramiko

        logger.debug("Connecting to %s:%s..." % (hostname, port))
        lfk = (not username and not pkey_path)
        sshc = paramiko.SSHClient()
        sshc.load_system_host_keys()
        sshc.set_missing_host_key_policy(paramiko.WarningPolicy())
        sshc.connect(
            hostname, port=port,
            username=username, password=password,
            key_filename=pkey_path,
            look_for_keys=lfk)
        try:
            logger.info("Connected as %s" %
                        sshc.get_transport().get_username())
            client = sshc.open_sftp()
            try:
                self._upload(sshc, client, ctx, path)
            finally:
                client.close()
        finally:
            sshc.close()

    def _previewUpload(self, ctx, dest_dir):
        if not ctx.args.force:
            logger.info("Would upload new/changed files...")
        else:
            logger.info("Would upload entire website...")

    def _upload(self, session, client, ctx, dest_dir):
        if dest_dir:
            if dest_dir.startswith('~/'):
                _, out_chan, _ = session.exec_command("echo $HOME")
                home_dir = out_chan.read().decode('utf8').strip()
                dest_dir = home_dir + dest_dir[1:]
            logger.debug("CHDIR %s" % dest_dir)
            try:
                client.chdir(dest_dir)
            except IOError:
                client.mkdir(dest_dir)
                client.chdir(dest_dir)

        known_dirs = {}
        if ctx.was_baked and not ctx.args.force:
            to_upload = list(self.getBakedFiles(ctx))
            to_delete = list(self.getDeletedFiles(ctx))
            if to_upload or to_delete:
                logger.info("Uploading new/changed files...")
                for path in self.getBakedFiles(ctx):
                    rel_path = os.path.relpath(path, ctx.bake_out_dir)
                    logger.info(rel_path)
                    if not ctx.preview:
                        self._putFile(client, path, rel_path, known_dirs)
                logger.info("Deleting removed files...")
                for path in self.getDeletedFiles(ctx):
                    rel_path = os.path.relpath(path, ctx.bake_out_dir)
                    logger.info("%s [DELETE]" % rel_path)
                    if not ctx.preview:
                        try:
                            client.remove(rel_path)
                        except OSError:
                            pass
            else:
                logger.info(
                    "Nothing to upload or delete on the remote server.")
                logger.info(
                    "If you want to force uploading the entire website, "
                    "use the `--force` flag.")
        else:
            logger.info("Uploading entire website...")
            for dirpath, dirnames, filenames in os.walk(ctx.bake_out_dir):
                for f in filenames:
                    abs_f = os.path.join(dirpath, f)
                    rel_f = os.path.relpath(abs_f, ctx.bake_out_dir)
                    logger.info(rel_f)
                    if not ctx.preview:
                        self._putFile(client, abs_f, rel_f, known_dirs)

    def _putFile(self, client, local_path, remote_path, known_dirs):
        # Split the remote path in bits.
        remote_path = os.path.normpath(remote_path)
        if os.sep != '/':
            remote_path = remote_path.sub(os.sep, '/')

        # Make sure each directory in the remote path exists... to prevent
        # testing the same directories several times, we keep a cache of
        # `known_dirs` which we know exist.
        remote_bits = remote_path.split('/')
        cur = ''
        for b in remote_bits[:-1]:
            cur = os.path.join(cur, b)
            if cur not in known_dirs:
                try:
                    client.stat(cur)
                except FileNotFoundError:
                    logger.debug("Creating remote dir: %s" % cur)
                    client.mkdir(cur)
                known_dirs[cur] = True

        # Should be all good! Upload the file.
        client.put(local_path, remote_path)

