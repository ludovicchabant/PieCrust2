import os
import os.path
import hashlib
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
        self._tmp_dir = None
        self._conf = None

    def initialize(self, app):
        super(BrowserifyProcessor, self).initialize(app)

        self._conf = app.config.get('browserify')
        if self._conf is None:
            return

        if self._conf is True:
            self._conf = {}

        bin_name = 'browserify'
        if platform.system() == 'Windows':
            bin_name += '.cmd'
        self._conf.setdefault('bin', bin_name)

    def onPipelineStart(self, ctx):
        self._tmp_dir = ctx.tmp_dir

    def matches(self, path):
        return self._conf is not None and os.path.splitext(path)[1] == '.js'

    def getDependencies(self, path):
        deps_path = self._getDepListPath(path)
        try:
            with open(deps_path, 'r', encoding='utf8') as f:
                deps_list = f.read()
        except OSError:
            logger.debug("No dependency list found for Browserify target '%s' "
                         "at '%s'. Rebuilding" % (path, deps_path))
            return FORCE_BUILD

        deps_list = [d.strip() for d in deps_list.split('\n')]
        return filter(lambda d: d, deps_list)

    def getOutputFilenames(self, filename):
        return [filename]

    def process(self, path, out_dir):
        # Update the dependency list file.
        # Sadly there doesn't seem to be a way to get the list at the same
        # time as compiling the bundle so we need to run the process twice :(
        deps_list = self._runBrowserify([path, '--list'])
        deps_list = deps_list.decode('utf8')
        deps_path = self._getDepListPath(path)
        with open(deps_path, 'w', encoding='utf8') as f:
            f.write(deps_list)

        # Actually compile the JS bundle.
        out_path = os.path.join(out_dir, os.path.basename(path))
        self._runBrowserify([path, '-o', out_path])

        return True

    def _runBrowserify(self, args):
        args = [self._conf['bin']] + args
        cwd = self.app.root_dir
        logger.debug("Running Browserify: %s" % ' '.join(args))
        try:
            return subprocess.check_output(
                args,
                cwd=cwd,
                stderr=subprocess.STDOUT)
        except FileNotFoundError as ex:
            logger.error("Tried running Browserify with command: %s" % args)
            raise Exception("Error running Browserify. "
                            "Did you install it?") from ex
        except subprocess.CalledProcessError as ex:
            logger.error("Error occured while running Browserify:")
            logger.info(ex.stdout)
            logger.error(ex.stderr)
            raise Exception("Error occured while running Browserify. "
                            "Please check log messages above for "
                            "more information.")

    def _getDepListPath(self, path):
        deps_name = "%s_%s.deps" % (
            os.path.basename(path),
            hashlib.md5(path.encode('utf8')).hexdigest())
        deps_path = os.path.join(self._tmp_dir, deps_name)
        return deps_path

