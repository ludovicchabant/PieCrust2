import os
import os.path
import logging
import platform
import subprocess
from piecrust.processing.base import Processor, PRIORITY_FIRST, FORCE_BUILD


logger = logging.getLogger(__name__)


class RequireJSProcessor(Processor):
    PROCESSOR_NAME = 'requirejs'

    def __init__(self):
        super(RequireJSProcessor, self).__init__()
        self.is_bypassing_structured_processing = True
        self._conf = None

    def initialize(self, app):
        super(RequireJSProcessor, self).initialize(app)

        self._conf = app.config.get('requirejs')
        if self._conf is None:
            return

        if 'build_path' not in self._conf:
            raise Exception("You need to specify `requirejs/build_path` "
                            "for RequireJS.")
        self._conf.setdefault('bin', 'r.js')
        self._conf.setdefault('out_path', self._conf['build_path'])

    def onPipelineStart(self, ctx):
        super(RequireJSProcessor, self).onPipelineStart(ctx)

        if self._conf is None:
            return

        logger.debug("Adding Javascript suppressor to build pipeline.")
        skip = _JavascriptSkipProcessor(self._conf['build_path'])
        ctx.extra_processors.append(skip)

    def matches(self, path):
        if self._conf is None:
            return False
        return path == self._conf['build_path']

    def getDependencies(self, path):
        return FORCE_BUILD

    def process(self, path, out_dir):
        args = [self._conf['bin'], '-o', path]
        shell = (platform.system() == 'Windows')
        cwd = self.app.root_dir
        logger.debug("Running RequireJS: %s" % ' '.join(args))
        try:
            retcode = subprocess.call(args, shell=shell, cwd=cwd)
        except FileNotFoundError as ex:
            logger.error("Tried running RequireJS processor "
                         "with command: %s" % args)
            raise Exception("Error running RequireJS. "
                            "Did you install it?") from ex
        if retcode != 0:
            raise Exception("Error occured in RequireJS compiler. "
                            "Please check log messages above for "
                            "more information.")
        return True


class _JavascriptSkipProcessor(Processor):
    PROCESSOR_NAME = 'requirejs_javascript_skip'

    def __init__(self, except_path=None):
        super(_JavascriptSkipProcessor, self).__init__()
        self.priority = PRIORITY_FIRST
        self.is_bypassing_structured_processing = True
        self._except_path = except_path

    def matches(self, path):
        _, ext = os.path.splitext(path)
        return ext == '.js' and path != self._except_path

    def process(self, in_path, out_path):
        return False

