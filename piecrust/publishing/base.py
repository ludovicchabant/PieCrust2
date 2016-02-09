import os.path
import shlex
import logging
import threading
import subprocess


logger = logging.getLogger(__name__)


class PublishingContext(object):
    def __init__(self):
        self.bake_out_dir = None
        self.preview = False


class Publisher(object):
    def __init__(self, app, target):
        self.app = app
        self.target = target
        self.parsed_url = None
        self.log_file_path = None

    @property
    def has_url_config(self):
        return self.parsed_url is not None

    @property
    def url_config(self):
        if self.parsed_url is not None:
            return self.getConfig()
        raise Exception("This publisher has a full configuration.")

    def getConfig(self):
        return self.app.config.get('publish/%s' % self.target)

    def getConfigValue(self, name):
        if self.has_url_config:
            raise Exception("This publisher only has a URL configuration.")
        return self.app.config.get('publish/%s/%s' % (self.target, name))

    def run(self, ctx):
        raise NotImplementedError()


class ShellCommandPublisherBase(Publisher):
    def __init__(self, app, target):
        super(ShellCommandPublisherBase, self).__init__(app, target)
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
                stdout=subprocess.PIPE)

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

