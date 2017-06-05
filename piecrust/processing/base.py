import os.path
import logging


logger = logging.getLogger(__name__)


PRIORITY_FIRST = -1
PRIORITY_NORMAL = 0
PRIORITY_LAST = 1


FORCE_BUILD = object()


class ProcessorContext:
    def __init__(self, pipeline):
        self.ignore_patterns = []
        self.extra_processors = []
        self._pipeline = pipeline
        self._pipeline_ctx = pipeline.ctx

    @property
    def tmp_dir(self):
        return self._pipeline.tmp_dir

    @property
    def out_dir(self):
        return self._pipeline_ctx.out_dir

    @property
    def worker_id(self):
        return self._pipeline_ctx.worker_id

    @property
    def is_main_process(self):
        return self._pipeline_ctx.is_main_process


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


class ExternalProcessException(Exception):
    def __init__(self, stderr_data):
        self.stderr_data = stderr_data

    def __str__(self):
        return self.stderr_data


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

