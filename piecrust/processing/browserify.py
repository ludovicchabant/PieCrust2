import os
import os.path
import logging
import platform
import subprocess
from piecrust.processing.base import Processor, PRIORITY_FIRST, FORCE_BUILD


logger = logging.getLogger(__name__)


class BrowserifyProcessor(Processor):
    PROCESSOR_NAME = 'browserify'

    def __init__(self):
        super(BrowserifyProcessor, self).__init__()
        self.priority = PRIORITY_FIRST
        self.is_delegating_dependency_check = False
        self._conf = None

    def initialize(self, app):
        super(BrowserifyProcessor, self).initialize(app)

        self._conf = app.config.get('browserify')
        if self._conf is None:
            return

        if self._conf is True:
            self._conf = {}

        self._conf.setdefault('bin', 'browserify')

    def matches(self, path):
        return self._conf is not None and os.path.splitext(path)[1] == '.js'

    def getDependencies(self, path):
        return FORCE_BUILD

    def getOutputFilenames(self, filename):
        return [filename]

    def process(self, path, out_dir):
        out_path = os.path.join(out_dir, os.path.basename(path))

        args = [self._conf['bin'], path, '-o', out_path]
        cwd = self.app.root_dir
        logger.debug("Running Browserify: %s" % ' '.join(args))
        try:
            retcode = subprocess.call(args, cwd=cwd)
        except FileNotFoundError as ex:
            logger.error("Tried running Browserify processor "
                         "with command: %s" % args)
            raise Exception("Error running Browserify. "
                            "Did you install it?") from ex
        if retcode != 0:
            raise Exception("Error occured in Browserify compiler. "
                            "Please check log messages above for "
                            "more information.")
        return True
