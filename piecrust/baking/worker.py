import time
import logging
from piecrust.app import PieCrust, apply_variant_and_values
from piecrust.baking.records import BakeRecord, _get_transition_key
from piecrust.baking.single import PageBaker, BakingError
from piecrust.environment import AbortedSourceUseError
from piecrust.rendering import (
        QualifiedPage, PageRenderingContext, render_page_segments)
from piecrust.routing import create_route_metadata
from piecrust.sources.base import PageFactory
from piecrust.workerpool import IWorker


logger = logging.getLogger(__name__)


class BakeWorkerContext(object):
    def __init__(self, appfactory, out_dir, *,
                 force=False, previous_record_path=None):
        self.appfactory = appfactory
        self.out_dir = out_dir
        self.force = force
        self.previous_record_path = previous_record_path
        self.app = None
        self.previous_record = None
        self.previous_record_index = None


class BakeWorker(IWorker):
    def __init__(self, ctx):
        self.ctx = ctx
        self.work_start_time = time.perf_counter()

    def initialize(self):
        # Create the app local to this worker.
        app = self.ctx.appfactory.create()
        app.config.set('baker/is_baking', True)
        app.config.set('baker/worker_id', self.wid)
        app.env.base_asset_url_format = '%uri%'
        app.env.fs_cache_only_for_main_page = True
        app.env.registerTimer("BakeWorker_%d_Total" % self.wid)
        app.env.registerTimer("BakeWorkerInit")
        app.env.registerTimer("JobReceive")
        app.env.registerManifest("LoadJobs")
        app.env.registerManifest("RenderJobs")
        app.env.registerManifest("BakeJobs")
        self.ctx.app = app

        # Load previous record
        if self.ctx.previous_record_path:
            self.ctx.previous_record = BakeRecord.load(
                    self.ctx.previous_record_path)
            self.ctx.previous_record_index = {}
            for e in self.ctx.previous_record.entries:
                key = _get_transition_key(e.path, e.taxonomy_info)
                self.ctx.previous_record_index[key] = e

        # Create the job handlers.
        job_handlers = {
                JOB_LOAD: LoadJobHandler(self.ctx),
                JOB_RENDER_FIRST: RenderFirstSubJobHandler(self.ctx),
                JOB_BAKE: BakeJobHandler(self.ctx)}
        for jt, jh in job_handlers.items():
            app.env.registerTimer(type(jh).__name__)
        self.job_handlers = job_handlers

        app.env.stepTimerSince("BakeWorkerInit", self.work_start_time)

    def process(self, job):
        handler = self.job_handlers[job['type']]
        with self.ctx.app.env.timerScope(type(handler).__name__):
            return handler.handleJob(job['job'])

    def getReport(self):
        self.ctx.app.env.stepTimerSince("BakeWorker_%d_Total" % self.wid,
                                        self.work_start_time)
        data = self.ctx.app.env.getStats()
        return {
                'type': 'stats',
                'data': data}


JOB_LOAD, JOB_RENDER_FIRST, JOB_BAKE = range(0, 3)


class JobHandler(object):
    def __init__(self, ctx):
        self.ctx = ctx

    @property
    def app(self):
        return self.ctx.app

    def handleJob(self, job):
        raise NotImplementedError()


def _get_errors(ex):
    errors = []
    while ex is not None:
        errors.append(str(ex))
        ex = ex.__cause__
    return errors


def save_factory(fac):
    return {
            'source_name': fac.source.name,
            'rel_path': fac.rel_path,
            'metadata': fac.metadata}


def load_factory(app, info):
    source = app.getSource(info['source_name'])
    return PageFactory(source, info['rel_path'], info['metadata'])


class LoadJobHandler(JobHandler):
    def handleJob(self, job):
        # Just make sure the page has been cached.
        fac = load_factory(self.app, job)
        logger.debug("Loading page: %s" % fac.ref_spec)
        self.app.env.addManifestEntry('LoadJobs', fac.ref_spec)
        result = {
                'source_name': fac.source.name,
                'path': fac.path,
                'config': None,
                'errors': None}
        try:
            page = fac.buildPage()
            page._load()
            result['config'] = page.config.getAll()
        except Exception as ex:
            logger.debug("Got loading error. Sending it to master.")
            result['errors'] = _get_errors(ex)
            if self.ctx.app.debug:
                logger.exception(ex)
        return result


class RenderFirstSubJobHandler(JobHandler):
    def handleJob(self, job):
        # Render the segments for the first sub-page of this page.
        fac = load_factory(self.app, job)
        self.app.env.addManifestEntry('RenderJobs', fac.ref_spec)

        # These things should be OK as they're checked upstream by the baker.
        route = self.app.getRoute(fac.source.name, fac.metadata,
                                  skip_taxonomies=True)
        assert route is not None

        page = fac.buildPage()
        route_metadata = create_route_metadata(page)
        qp = QualifiedPage(page, route, route_metadata)
        ctx = PageRenderingContext(qp)
        self.app.env.abort_source_use = True

        result = {
                'path': fac.path,
                'aborted': False,
                'errors': None}
        logger.debug("Preparing page: %s" % fac.ref_spec)
        try:
            render_page_segments(ctx)
        except AbortedSourceUseError:
            logger.debug("Page %s was aborted." % fac.ref_spec)
            result['aborted'] = True
        except Exception as ex:
            logger.debug("Got rendering error. Sending it to master.")
            result['errors'] = _get_errors(ex)
            if self.ctx.app.debug:
                logger.exception(ex)
        finally:
            self.app.env.abort_source_use = False
        return result


class BakeJobHandler(JobHandler):
    def __init__(self, ctx):
        super(BakeJobHandler, self).__init__(ctx)
        self.page_baker = PageBaker(ctx.app, ctx.out_dir, ctx.force)

    def handleJob(self, job):
        # Actually bake the page and all its sub-pages to the output folder.
        fac = load_factory(self.app, job['factory_info'])
        self.app.env.addManifestEntry('BakeJobs', fac.ref_spec)

        route_metadata = job['route_metadata']
        tax_info = job['taxonomy_info']
        if tax_info is not None:
            route = self.app.getTaxonomyRoute(tax_info.taxonomy_name,
                                              tax_info.source_name)
        else:
            route = self.app.getRoute(fac.source.name, route_metadata,
                                      skip_taxonomies=True)
        assert route is not None

        page = fac.buildPage()
        qp = QualifiedPage(page, route, route_metadata)

        result = {
                'path': fac.path,
                'taxonomy_info': tax_info,
                'sub_entries': None,
                'errors': None}
        dirty_source_names = job['dirty_source_names']

        previous_entry = None
        if self.ctx.previous_record_index is not None:
            key = _get_transition_key(fac.path, tax_info)
            previous_entry = self.ctx.previous_record_index.get(key)

        logger.debug("Baking page: %s" % fac.ref_spec)
        try:
            sub_entries = self.page_baker.bake(
                    qp, previous_entry, dirty_source_names, tax_info)
            result['sub_entries'] = sub_entries

        except BakingError as ex:
            logger.debug("Got baking error. Sending it to master.")
            result['errors'] = _get_errors(ex)
            if self.ctx.app.debug:
                logger.exception(ex)

        return result

