import os
import os.path
import logging
import subprocess
from piecrust.processing.base import Processor, PRIORITY_FIRST
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


class CompassProcessor(Processor):
    PROCESSOR_NAME = 'compass'

    STATE_UNKNOWN = 0
    STATE_INACTIVE = 1
    STATE_ACTIVE = 2

    def __init__(self):
        super(CompassProcessor, self).__init__()
        # Using a high priority is needed to get to the `.scss` files before
        # the Sass processor.
        self.priority = PRIORITY_FIRST
        self.is_bypassing_structured_processing = True
        self.is_delegating_dependency_check = False
        self._state = self.STATE_UNKNOWN

    def initialize(self, app):
        super(CompassProcessor, self).initialize(app)

    def onPipelineStart(self, ctx):
        super(CompassProcessor, self).onPipelineStart(ctx)
        self._maybeActivate(ctx)

    def onPipelineEnd(self, ctx):
        super(CompassProcessor, self).onPipelineEnd(ctx)
        self._maybeRunCompass(ctx)

    def matches(self, path):
        if self._state != self.STATE_ACTIVE:
            return False

        _, ext = os.path.splitext(path)
        return ext == '.scss' or ext == '.sass'

    def getDependencies(self, path):
        raise Exception("Compass processor should handle dependencies by "
                        "itself.")

    def getOutputFilenames(self, filename):
        raise Exception("Compass processor should handle outputs by itself.")

    def process(self, path, out_dir):
        if path.startswith(self.app.theme_dir):
            if not self._runInTheme:
                logger.debug("Scheduling Compass execution in theme directory "
                             "after the pipeline is done.")
                self._runInTheme = True
        else:
            if not self._runInSite:
                logger.debug("Scheduling Compass execution after the pipeline "
                             "is done.")
                self._runInSite = True

    def _maybeActivate(self, ctx):
        if self._state != self.STATE_UNKNOWN:
            return

        config = self.app.config.get('compass')
        if config is None or not config.get('enable'):
            self._state = self.STATE_INACTIVE
            return

        logger.debug("Activating Compass processing for SCSS/SASS files.")
        self._state = self.STATE_ACTIVE

        bin_path = config.get('bin', 'compass')

        config_path = config.get('config_path', 'config.rb')
        config_path = os.path.join(self.app.root_dir, config_path)
        if not os.path.exists(config_path):
            raise Exception("Can't find Compass configuration file: %s" %
                            config_path)
        self._args = '%s compile --config "%s"' % (bin_path, config_path)

        frameworks = config.get('frameworks', [])
        if not isinstance(frameworks, list):
            frameworks = frameworks.split(',')
        for f in frameworks:
            self._args += ' --load %s' % f

        custom_args = config.get('options')
        if custom_args:
            self._args += ' ' + custom_args

        out_dir = ctx.out_dir
        tmp_dir = os.path.join(ctx.tmp_dir, 'compass')
        self._args = multi_replace(
            self._args,
            {'%out_dir%': out_dir,
             '%tmp_dir%': tmp_dir})

        self._runInSite = False
        self._runInTheme = False

    def _maybeRunCompass(self, ctx):
        if self._state != self.STATE_ACTIVE:
            return

        logger.debug("Running Compass with:")
        logger.debug(self._args)

        prev_cwd = os.getcwd()
        os.chdir(self.app.root_dir)
        try:
            retcode = subprocess.call(self._args, shell=True)
        except FileNotFoundError as ex:
            logger.error("Tried running Compass with command: %s" %
                         self._args)
            raise Exception("Error running Compass. "
                            "Did you install it?") from ex
        finally:
            os.chdir(prev_cwd)

        if retcode != 0:
            raise Exception("Error occured in Compass. Please check "
                            "log messages above for more information.")
        return True

