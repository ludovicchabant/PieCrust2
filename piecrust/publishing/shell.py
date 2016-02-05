import sys
import shlex
import logging
import threading
import subprocess
from piecrust.publishing.base import Publisher


logger = logging.getLogger(__name__)


class ShellCommandPublisher(Publisher):
    PUBLISHER_NAME = 'shell'

    def __init__(self, app, target):
        super(ShellCommandPublisher, self).__init__(app, target)
        self.is_using_custom_logging = True

    def run(self, ctx):
        target_cmd = self.getConfigValue('cmd')
        if not target_cmd:
            raise Exception("No command specified for publish target: %s" %
                            self.target)
        args = shlex.split(target_cmd)

        logger.debug(
                "Running shell command: %s" % args)

        proc = subprocess.Popen(
                args, cwd=self.app.root_dir, bufsize=0,
                stdout=subprocess.PIPE,
                universal_newlines=False)

        logger.debug("Running publishing monitor for PID %d" % proc.pid)
        thread = _PublishThread(proc, ctx.custom_logging_file)
        thread.start()
        proc.wait()
        thread.join()

        if proc.returncode != 0:
            logger.error(
                    "Publish process returned code %d" % proc.returncode)
        else:
            logger.debug("Publish process returned successfully.")

        return proc.returncode == 0


class _PublishThread(threading.Thread):
    def __init__(self, proc, log_fp):
        super(_PublishThread, self).__init__(
                name='publish_monitor', daemon=True)
        self.proc = proc
        self.log_fp = log_fp

    def run(self):
        for line in iter(self.proc.stdout.readline, b''):
            line_str = line.decode('utf8')
            sys.stdout.write(line_str)
            sys.stdout.flush()
            if self.log_fp:
                self.log_fp.write(line_str)
                self.log_fp.flush()

        self.proc.communicate()
        logger.debug("Publish monitor exiting.")

