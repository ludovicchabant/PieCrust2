import os
import os.path
import logging
import platform
import subprocess
from piecrust.processing.base import Processor, SimpleFileProcessor


logger = logging.getLogger(__name__)


class CleanCssProcessor(Processor):
    PROCESSOR_NAME = 'cleancss'

    def __init__(self):
        super(CleanCssProcessor, self).__init__()
        self._conf = None

    def matches(self, path):
        return path.endswith('.css')

    def getOutputFilenames(self, filename):
        self._ensureInitialized()
        basename, _ = os.path.splitext(filename)
        return ['%s%s' % (basename, self._conf['out_ext'])]

    def process(self, path, out_dir):
        self._ensureInitialized()

        _, in_name = os.path.split(path)
        out_name = self.getOutputFilenames(in_name)[0]
        out_path = os.path.join(out_dir, out_name)

        args = [self._conf['bin'], '-o', out_path]
        args += self._conf['options']
        args.append(path)
        logger.debug("Cleaning CSS file: %s" % args)

        # On Windows, we need to run the process in a shell environment
        # otherwise it looks like `PATH` isn't taken into account.
        shell = (platform.system() == 'Windows')
        try:
            retcode = subprocess.call(args, shell=shell)
        except FileNotFoundError as ex:
            logger.error("Tried running CleanCSS processor with command: %s" %
                         args)
            raise Exception("Error running CleanCSS processor. "
                            "Did you install it?") from ex
        if retcode != 0:
            raise Exception("Error occured in CleanCSS. Please check "
                            "log messages above for more information.")
        return True

    def _ensureInitialized(self):
        if self._conf is not None:
            return

        self._conf = self.app.config.get('cleancss') or {}
        self._conf.setdefault('bin', 'cleancss')
        self._conf.setdefault('options', ['--skip-rebase'])
        self._conf.setdefault('out_ext', '.css')
        if len(self._conf['out_ext']) > 0 and self._conf['out_ext'][0] != '.':
            self._conf['out_ext'] = '.' + self._conf['out_ext']
        if not isinstance(self._conf['options'], list):
            raise Exception("The `cleancss/options` configuration setting "
                            "must be an array of arguments.")


class UglifyJSProcessor(SimpleFileProcessor):
    PROCESSOR_NAME = 'uglifyjs'

    def __init__(self):
        super(UglifyJSProcessor, self).__init__({'js': 'js'})
        self._conf = None

    def _doProcess(self, in_path, out_path):
        self._ensureInitialized()

        args = [self._conf['bin'], in_path, '-o', out_path]
        args += self._conf['options']
        logger.debug("Uglifying JS file: %s" % args)

        # On Windows, we need to run the process in a shell environment
        # otherwise it looks like `PATH` isn't taken into account.
        shell = (platform.system() == 'Windows')
        try:
            retcode = subprocess.call(args, shell=shell)
        except FileNotFoundError as ex:
            logger.error("Tried running UglifyJS processor with command: %s" %
                         args)
            raise Exception("Error running UglifyJS processor. "
                            "Did you install it?") from ex
        if retcode != 0:
            raise Exception("Error occured in UglifyJS. Please check "
                            "log messages above for more information.")
        return True

    def _ensureInitialized(self):
        if self._conf is not None:
            return

        self._conf = self.app.config.get('uglifyjs') or {}
        self._conf.setdefault('bin', 'uglifyjs')
        self._conf.setdefault('options', ['--compress'])
        if not isinstance(self._conf['options'], list):
            raise Exception("The `uglify/options` configuration setting "
                            "must be an array of arguments.")

