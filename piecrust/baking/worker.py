import time
import logging
from piecrust.pipelines.base import (
    PipelineManager, PipelineJobRunContext, PipelineJobResult,
    get_pipeline_name_for_source)
from piecrust.pipelines.records import (
    MultiRecordHistory, MultiRecord, load_records)
from piecrust.workerpool import IWorker


logger = logging.getLogger(__name__)


class BakeWorkerContext(object):
    def __init__(self, appfactory, out_dir, *,
                 force=False, previous_records_path=None,
                 allowed_pipelines=None, forbidden_pipelines=None):
        self.appfactory = appfactory
        self.out_dir = out_dir
        self.force = force
        self.previous_records_path = previous_records_path
        self.allowed_pipelines = allowed_pipelines
        self.forbidden_pipelines = forbidden_pipelines


class BakeWorker(IWorker):
    def __init__(self, ctx):
        self.ctx = ctx
        self.app = None
        self.record_histories = None
        self._work_start_time = time.perf_counter()
        self._sources = {}
        self._ppctx = None

    def initialize(self):
        # Create the app local to this worker.
        app = self.ctx.appfactory.create()
        app.config.set('baker/is_baking', True)
        app.config.set('baker/worker_id', self.wid)
        app.config.set('site/asset_url_format', '%page_uri%/%filename%')

        app.env.fs_cache_only_for_main_page = True

        stats = app.env.stats
        stats.registerTimer("BakeWorker_%d_Total" % self.wid)
        stats.registerTimer("BakeWorkerInit")

        self.app = app

        # Load previous record
        if self.ctx.previous_records_path:
            previous_records = load_records(self.ctx.previous_records_path)
        else:
            previous_records = MultiRecord()
        current_records = MultiRecord()
        self.record_histories = MultiRecordHistory(
            previous_records, current_records)

        # Create the pipelines.
        self.ppmngr = PipelineManager(
            app, self.ctx.out_dir, self.record_histories,
            worker_id=self.wid, force=self.ctx.force)
        ok_pp = self.ctx.allowed_pipelines
        nok_pp = self.ctx.forbidden_pipelines
        for src in app.sources:
            pname = get_pipeline_name_for_source(src)
            if ok_pp is not None and pname not in ok_pp:
                continue
            if nok_pp is not None and pname in nok_pp:
                continue

            self.ppmngr.createPipeline(src)

        stats.stepTimerSince("BakeWorkerInit", self._work_start_time)

    def process(self, job):
        item = job.content_item
        logger.debug("Received job: %s@%s" % (job.source_name, item.spec))

        ppinfo = self.ppmngr.getPipeline(job.source_name)
        pp = ppinfo.pipeline

        runctx = PipelineJobRunContext(job, pp.record_name,
                                       self.record_histories)

        ppres = PipelineJobResult()
        # For subsequent pass jobs, there will be a record entry given. For
        # first pass jobs, there's none so we get the pipeline to create it.
        ppres.record_entry = job.data.get('record_entry')
        if ppres.record_entry is None:
            ppres.record_entry = pp.createRecordEntry(job, runctx)
        pp.run(job, runctx, ppres)
        return ppres

    def getStats(self):
        stats = self.app.env.stats
        stats.stepTimerSince("BakeWorker_%d_Total" % self.wid,
                             self._work_start_time)
        return stats

    def shutdown(self):
        for src, pp in self._sources.values():
            pp.shutdown(self._ppctx)

