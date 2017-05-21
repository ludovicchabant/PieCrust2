import os.path
import logging


logger = logging.getLogger(__name__)


class PipelineContext:
    """ The context for running a content pipeline.
    """
    def __init__(self, out_dir, record_history, *,
                 worker_id=-1, force=None):
        self.out_dir = out_dir
        self.record_history = record_history
        self.worker_id = worker_id
        self.force = force

    @property
    def is_worker(self):
        """ Returns `True` if the content pipeline is running inside
            a worker process, and this is the first one.
        """
        return self.worker_id >= 0

    @property
    def is_main_process(self):
        """ Returns `True` is the content pipeline is running inside
            the main process (and not a worker process). This is the case
            if there are no worker processes at all.
        """
        return self.worker_id < 0

    @property
    def current_record(self):
        return self.record_history.current


class PipelineResult:
    """ Result of running a pipeline on a content item.
    """
    def __init__(self):
        self.pipeline_name = None
        self.record_entry = None


class ContentPipeline:
    """ A pipeline that processes content from a `ContentSource`.
    """
    PIPELINE_NAME = None
    PIPELINE_PASSES = 1
    RECORD_ENTRY_CLASS = None

    def __init__(self, source):
        self.source = source

        app = source.app
        tmp_dir = app.cache_dir
        if not tmp_dir:
            import tempfile
            tmp_dir = os.path.join(tempfile.gettempdir(), 'piecrust')
        self.tmp_dir = os.path.join(tmp_dir, self.PIPELINE_NAME)

    @property
    def app(self):
        return self.source.app

    def initialize(self, ctx):
        pass

    def run(self, content_item, ctx, result):
        raise NotImplementedError()

    def getDeletions(self, ctx):
        pass

    def collapseRecords(self, ctx):
        pass

    def shutdown(self, ctx):
        pass
