import os.path
import logging
from werkzeug.utils import cached_property
from piecrust.configuration import ConfigurationError


logger = logging.getLogger(__name__)


class PipelineContext:
    """ The context for running a content pipeline.
    """
    def __init__(self, out_dir, *,
                 worker_id=-1, force=None):
        self.out_dir = out_dir
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


class _PipelineMasterProcessJobContextBase:
    def __init__(self, record_name, record_histories):
        self.record_name = record_name
        self.record_histories = record_histories

    @property
    def previous_record(self):
        return self.record_histories.getPreviousRecord(self.record_name)

    @property
    def current_record(self):
        return self.record_histories.getCurrentRecord(self.record_name)


class PipelineJobCreateContext(_PipelineMasterProcessJobContextBase):
    """ Context for creating pipeline baking jobs.

        This is run on the master process, so it can access both the
        previous and current records.
    """
    def __init__(self, pass_num, record_name, record_histories):
        super().__init__(record_name, record_histories)
        self.pass_num = pass_num


class PipelineJobRunContext:
    """ Context for running pipeline baking jobs.

        This is run on the worker processes, so it can only access the
        previous records.
    """
    def __init__(self, job, record_name, previous_records):
        self.job = job
        self.record_name = record_name
        self.previous_records = previous_records

    @cached_property
    def record_entry_spec(self):
        return self.job.get('record_entry_spec',
                            self.job['job_spec'][1])

    @cached_property
    def previous_record(self):
        return self.previous_records.getRecord(self.record_name)

    @cached_property
    def previous_entry(self):
        return self.previous_record.getEntry(self.record_entry_spec)


class PipelineJobResultHandleContext:
    """ The context for handling the result from a job that ran in a
        worker process.

        This is run on the master process, so it can access the current
        record.
    """
    def __init__(self, record, job, pass_num):
        self.record = record
        self.job = job
        self.pass_num = pass_num

    @cached_property
    def record_entry(self):
        record_entry_spec = self.job.get('record_entry_spec',
                                         self.job['job_spec'][1])
        return self.record.getEntry(record_entry_spec)


class PipelinePostJobRunContext:
    def __init__(self, record_history):
        self.record_history = record_history


class PipelineDeletionContext:
    def __init__(self, record_history):
        self.record_history = record_history


class PipelineCollapseRecordContext:
    def __init__(self, record_history):
        self.record_history = record_history


class ContentPipeline:
    """ A pipeline that processes content from a `ContentSource`.
    """
    PIPELINE_NAME = None
    RECORD_ENTRY_CLASS = None
    PASS_NUM = 0

    def __init__(self, source, ctx):
        self.source = source
        self.ctx = ctx
        self.record_name = '%s@%s' % (source.name, self.PIPELINE_NAME)

        app = source.app
        tmp_dir = app.cache_dir
        if not tmp_dir:
            import tempfile
            tmp_dir = os.path.join(tempfile.gettempdir(), 'piecrust')
        self.tmp_dir = os.path.join(tmp_dir, self.PIPELINE_NAME)

    @property
    def app(self):
        return self.source.app

    def initialize(self):
        pass

    def createJobs(self, ctx):
        return [
            create_job(self, item.spec)
            for item in self.source.getAllContents()], None

    def createRecordEntry(self, item_spec):
        entry_class = self.RECORD_ENTRY_CLASS
        record_entry = entry_class()
        record_entry.item_spec = item_spec
        return record_entry

    def handleJobResult(self, result, ctx):
        raise NotImplementedError()

    def run(self, job, ctx, result):
        raise NotImplementedError()

    def postJobRun(self, ctx):
        pass

    def getDeletions(self, ctx):
        pass

    def collapseRecords(self, ctx):
        pass

    def shutdown(self):
        pass


def create_job(pipeline, item_spec, **kwargs):
    job = {
        'job_spec': (pipeline.source.name, item_spec)
    }
    job.update(kwargs)
    return job


def content_item_from_job(pipeline, job):
    return pipeline.source.findContentFromSpec(job['job_spec'][1])


def get_record_name_for_source(source):
    ppname = get_pipeline_name_for_source(source)
    return '%s@%s' % (source.name, ppname)


def get_pipeline_name_for_source(source):
    pname = source.config['pipeline']
    if not pname:
        pname = source.DEFAULT_PIPELINE_NAME
    if not pname:
        raise ConfigurationError(
            "Source '%s' doesn't specify any pipeline." % source.name)
    return pname


class PipelineManager:
    def __init__(self, app, out_dir, *,
                 record_histories=None, worker_id=-1, force=False):
        self.app = app
        self.record_histories = record_histories
        self.out_dir = out_dir
        self.worker_id = worker_id
        self.force = force

        self._pipeline_classes = {}
        for pclass in app.plugin_loader.getPipelines():
            self._pipeline_classes[pclass.PIPELINE_NAME] = pclass

        self._pipelines = {}

    def getPipeline(self, source_name):
        return self.getPipelineInfo(source_name).pipeline

    def getPipelineInfo(self, source_name):
        return self._pipelines[source_name]

    def getPipelineInfos(self):
        return self._pipelines.values()

    def createPipeline(self, source):
        if source.name in self._pipelines:
            raise ValueError("Pipeline for source '%s' was already created." %
                             source.name)

        pname = get_pipeline_name_for_source(source)
        ppctx = PipelineContext(self.out_dir,
                                worker_id=self.worker_id, force=self.force)
        pp = self._pipeline_classes[pname](source, ppctx)
        pp.initialize()

        record_history = None
        if self.record_histories:
            record_history = self.record_histories.getHistory(pp.record_name)

        info = _PipelineInfo(pp, record_history)
        self._pipelines[source.name] = info
        return info

    def postJobRun(self):
        for ppinfo in self.getPipelineInfos():
            ppinfo.record_history.build()

        for ppinfo in self.getPipelineInfos():
            ctx = PipelinePostJobRunContext(ppinfo.record_history)
            ppinfo.pipeline.postJobRun(ctx)

    def deleteStaleOutputs(self):
        for ppinfo in self.getPipelineInfos():
            ctx = PipelineDeletionContext(ppinfo.record_history)
            to_delete = ppinfo.pipeline.getDeletions(ctx)
            current_record = ppinfo.record_history.current
            if to_delete is not None:
                for path, reason in to_delete:
                    logger.debug("Removing '%s': %s" % (path, reason))
                    current_record.deleted_out_paths.append(path)
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass
                    logger.info('[delete] %s' % path)

    def collapseRecords(self, keep_unused_records=False):
        seen_records = []
        for ppinfo in self.getPipelineInfos():
            ctx = PipelineCollapseRecordContext(ppinfo.record_history)
            ppinfo.pipeline.collapseRecords(ctx)
            seen_records.append(ppinfo.pipeline.record_name)

        if keep_unused_records:
            cur_recs = self.record_histories.current
            prev_recs = self.record_histories.previous
            for prev_rec in prev_recs.records:
                if prev_rec.name in seen_records:
                    continue

                logger.debug("Keeping record: %s" % prev_rec.name)
                cur_recs.records.append(prev_rec)

    def shutdownPipelines(self):
        for ppinfo in self.getPipelineInfos():
            ppinfo.pipeline.shutdown()

        self._pipelines = {}


class _PipelineInfo:
    def __init__(self, pipeline, record_history):
        self.pipeline = pipeline
        self.record_history = record_history
        self.userdata = None

    @property
    def source(self):
        return self.pipeline.source

    @property
    def current_record(self):
        if self.record_history is not None:
            return self.record_history.current
        raise Exception("The current record is not available.")

    @property
    def pipeline_name(self):
        return self.pipeline.PIPELINE_NAME

