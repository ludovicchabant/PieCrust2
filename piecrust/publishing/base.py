import os.path
import shlex
import urllib.parse
import logging
import threading
import subprocess
from piecrust.configuration import try_get_dict_value


logger = logging.getLogger(__name__)


FILE_MODIFIED = 1
FILE_DELETED = 2


class PublisherConfigurationError(Exception):
    pass


class PublishingContext(object):
    def __init__(self):
        self.bake_out_dir = None
        self.bake_record = None
        self.processing_record = None
        self.was_baked = False
        self.preview = False
        self.args = None


class Publisher(object):
    PUBLISHER_NAME = 'undefined'
    PUBLISHER_SCHEME = None

    def __init__(self, app, target, config):
        self.app = app
        self.target = target
        self.config = config
        self.has_url_config = isinstance(config, urllib.parse.ParseResult)
        self.log_file_path = None

    def setupPublishParser(self, parser, app):
        return

    def getConfigValue(self, name, default_value=None):
        if self.has_url_config:
            raise Exception("This publisher only has a URL configuration.")
        return try_get_dict_value(self.config, name, default=default_value)

    def run(self, ctx):
        raise NotImplementedError()

    def getBakedFiles(self, ctx):
        for e in ctx.bake_record.entries:
            for sub in e.subs:
                if sub.was_baked:
                    yield sub.out_path
        for e in ctx.processing_record.entries:
            if e.was_processed:
                yield from [os.path.join(ctx.processing_record.out_dir, p)
                        for p in e.rel_outputs]

    def getDeletedFiles(self, ctx):
        yield from ctx.bake_record.deleted
        yield from ctx.processing_record.deleted


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

