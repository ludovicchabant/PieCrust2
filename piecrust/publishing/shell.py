import os.path
import shlex
import logging
import threading
import subprocess
from piecrust.publishing.base import Publisher


logger = logging.getLogger(__name__)


class ShellCommandPublisherBase(Publisher):
    def __init__(self, app, target, config):
        super(ShellCommandPublisherBase, self).__init__(app, target, config)
        self.expand_user_args = True

    def run(self, ctx):
        args = self._getCommandArgs(ctx)
        if self.expand_user_args:
            args = [os.path.expanduser(i) for i in args]

        if ctx.preview:
            preview_args = ' '.join([shlex.quote(i) for i in args])
            logger.info(
                "Would run shell command: %s" % preview_args)
            return True

        logger.debug(
            "Running shell command: %s" % args)

        proc = subprocess.Popen(
            args, cwd=self.app.root_dir, bufsize=0,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        logger.debug("Running publishing monitor for PID %d" % proc.pid)
        thread = _PublishThread(proc)
        thread.start()
        proc.wait()
        thread.join()

        if proc.returncode != 0:
            logger.error(
                "Publish process returned code %d" % proc.returncode)
        else:
            logger.debug("Publish process returned successfully.")

        return proc.returncode == 0

    def _getCommandArgs(self, ctx):
        raise NotImplementedError()


class _PublishThread(threading.Thread):
    def __init__(self, proc):
        super(_PublishThread, self).__init__(
            name='publish_monitor', daemon=True)
        self.proc = proc
        self.root_logger = logging.getLogger()

    def run(self):
        for line in iter(self.proc.stdout.readline, b''):
            line_str = line.decode('utf8')
            logger.info(line_str.rstrip('\r\n'))
            for h in self.root_logger.handlers:
                h.flush()

        self.proc.communicate()
        logger.debug("Publish monitor exiting.")


class ShellCommandPublisher(ShellCommandPublisherBase):
    PUBLISHER_NAME = 'shell'

    def _getCommandArgs(self, ctx):
        target_cmd = self.config.get('command')
        if not target_cmd:
            raise Exception("No command specified for publish target: %s" %
                            self.target)
        args = shlex.split(target_cmd)
        return args

