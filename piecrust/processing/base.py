import shutil
import os.path
import logging


logger = logging.getLogger(__name__)


PRIORITY_FIRST = -1
PRIORITY_NORMAL = 0
PRIORITY_LAST = 1


class PipelineContext(object):
    def __init__(self, worker_id, app, out_dir, tmp_dir, force=None):
        self.worker_id = worker_id
        self.app = app
        self.out_dir = out_dir
        self.tmp_dir = tmp_dir
        self.force = force
        self.record = None
        self._additional_ignore_patterns = []

    @property
    def is_first_worker(self):
        return self.worker_id == 0

    @property
    def is_pipeline_process(self):
        return self.worker_id < 0

    def addIgnorePatterns(self, patterns):
        self._additional_ignore_patterns += patterns


class Processor(object):
    PROCESSOR_NAME = None

    def __init__(self):
        self.priority = PRIORITY_NORMAL
        self.is_bypassing_structured_processing = False
        self.is_delegating_dependency_check = True

    def initialize(self, app):
        self.app = app

    def onPipelineStart(self, ctx):
        pass

    def onPipelineEnd(self, ctx):
        pass

    def matches(self, path):
        return False

    def getDependencies(self, path):
        return None

    def getOutputFilenames(self, filename):
        return None

    def process(self, path, out_dir):
        pass


class CopyFileProcessor(Processor):
    PROCESSOR_NAME = 'copy'

    def __init__(self):
        super(CopyFileProcessor, self).__init__()
        self.priority = PRIORITY_LAST

    def matches(self, path):
        return True

    def getOutputFilenames(self, filename):
        return [filename]

    def process(self, path, out_dir):
        out_path = os.path.join(out_dir, os.path.basename(path))
        logger.debug("Copying: %s -> %s" % (path, out_path))
        shutil.copyfile(path, out_path)
        return True


class SimpleFileProcessor(Processor):
    def __init__(self, extensions=None):
        super(SimpleFileProcessor, self).__init__()
        self.extensions = extensions or {}

    def matches(self, path):
        for ext in self.extensions:
            if path.endswith('.' + ext):
                return True
        return False

    def getOutputFilenames(self, filename):
        basename, ext = os.path.splitext(filename)
        ext = ext.lstrip('.')
        out_ext = self.extensions[ext]
        return ['%s.%s' % (basename, out_ext)]

    def process(self, path, out_dir):
        _, in_name = os.path.split(path)
        out_name = self.getOutputFilenames(in_name)[0]
        out_path = os.path.join(out_dir, out_name)
        return self._doProcess(path, out_path)

    def _doProcess(self, in_path, out_path):
        raise NotImplementedError()


class ExternalProcessException(Exception):
    def __init__(self, stderr_data):
        self.stderr_data = stderr_data

    def __str__(self):
        return self.stderr_data


