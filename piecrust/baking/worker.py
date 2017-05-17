import time
import logging
from piecrust.pipelines.base import PipelineContext, PipelineResult
from piecrust.pipelines.records import (
    MultiRecordHistory, MultiRecord, Record, load_records)
from piecrust.sources.base import ContentItem
from piecrust.workerpool import IWorker


logger = logging.getLogger(__name__)


class BakeWorkerContext(object):
    def __init__(self, appfactory, out_dir, *,
                 force=False, previous_records_path=None,
                 allowed_pipelines=None):
        self.appfactory = appfactory
        self.out_dir = out_dir
        self.force = force
        self.previous_records_path = previous_records_path
        self.allowed_pipelines = allowed_pipelines


class BakeWorker(IWorker):
    def __init__(self, ctx):
        self.ctx = ctx
        self.app = None
        self.record_history = None
        self._work_start_time = time.perf_counter()
        self._sources = {}
        self._ppctx = None

    def initialize(self):
        # Create the app local to this worker.
        app = self.ctx.appfactory.create()
        app.config.set('baker/is_baking', True)
        app.config.set('baker/worker_id', self.wid)
        app.config.set('site/base_asset_url_format', '%uri')

        app.env.fs_cache_only_for_main_page = True

        stats = app.env.stats
        stats.registerTimer("BakeWorker_%d_Total" % self.wid)
        stats.registerTimer("BakeWorkerInit")
        stats.registerTimer("JobReceive")
        stats.registerTimer('LoadJob', raise_if_registered=False)
        stats.registerTimer('RenderFirstSubJob',
                            raise_if_registered=False)
        stats.registerTimer('BakeJob', raise_if_registered=False)

        stats.registerCounter("SourceUseAbortions")

        stats.registerManifest("LoadJobs")
        stats.registerManifest("RenderJobs")
        stats.registerManifest("BakeJobs")

        self.app = app

        # Load previous record
        if self.ctx.previous_records_path:
            previous_records = load_records(self.ctx.previous_records_path)
        else:
            previous_records = MultiRecord()
        current_records = MultiRecord()
        self.record_history = MultiRecordHistory(
            previous_records, current_records)

        # Cache sources and create pipelines.
        ppclasses = {}
        for ppclass in app.plugin_loader.getPipelines():
            ppclasses[ppclass.PIPELINE_NAME] = ppclass

        self._ppctx = PipelineContext(self.ctx.out_dir, self.record_history,
                                      worker_id=self.wid,
                                      force=self.ctx.force)
        for src in app.sources:
            ppname = src.config['pipeline']
            if (self.ctx.allowed_pipelines is not None and
                    ppname not in self.ctx.allowed_pipelines):
                continue

            pp = ppclasses[ppname](src)
            pp.initialize(self._ppctx)
            self._sources[src.name] = (src, pp)

        stats.stepTimerSince("BakeWorkerInit", self._work_start_time)

    def process(self, job):
        logger.debug("Received job: %s@%s" % (job.source_name, job.item_spec))
        src, pp = self._sources[job.source_name]
        item = ContentItem(job.item_spec, job.item_metadata)

        record_class = pp.RECORD_CLASS or Record
        ppres = PipelineResult(record_class())
        ppres.record.item_spec = job.item_spec
        pp.run(item, self._ppctx, ppres)
        return ppres

    def getStats(self):
        stats = self.app.env.stats
        stats.stepTimerSince("BakeWorker_%d_Total" % self.wid,
                             self._work_start_time)
        return stats

    def shutdown(self):
        for src, pp in self._sources.values():
            pp.shutdown(self._ppctx)


class BakeJob:
    def __init__(self, source_name, item_spec, item_metadata):
        self.source_name = source_name
        self.item_spec = item_spec
        self.item_metadata = item_metadata


class JobHandler:
    def __init__(self, ctx):
        self.ctx = ctx

    @property
    def app(self):
        return self.ctx.app

    def handleJob(self, job):
        raise NotImplementedError()

    def shutdown(self):
        pass


def _get_errors(ex):
    errors = []
    while ex is not None:
        errors.append(str(ex))
        ex = ex.__cause__
    return errors

