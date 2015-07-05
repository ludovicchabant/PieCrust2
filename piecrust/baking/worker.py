import time
import logging
from piecrust.app import PieCrust
from piecrust.baking.single import PageBaker, BakingError
from piecrust.rendering import (
        QualifiedPage, PageRenderingContext, render_page_segments)
from piecrust.routing import create_route_metadata
from piecrust.sources.base import PageFactory
from piecrust.workerpool import IWorker


logger = logging.getLogger(__name__)


class BakeWorkerContext(object):
    def __init__(self, root_dir, sub_cache_dir, out_dir,
                 force=False, debug=False):
        self.root_dir = root_dir
        self.sub_cache_dir = sub_cache_dir
        self.out_dir = out_dir
        self.force = force
        self.debug = debug


class BakeWorker(IWorker):
    def __init__(self, ctx):
        self.ctx = ctx
        self.work_start_time = time.perf_counter()

    def initialize(self):
        # Create the app local to this worker.
        app = PieCrust(self.ctx.root_dir, debug=self.ctx.debug)
        app._useSubCacheDir(self.ctx.sub_cache_dir)
        app.env.fs_cache_only_for_main_page = True
        app.env.registerTimer("BakeWorker_%d_Total" % self.wid)
        app.env.registerTimer("BakeWorkerInit")
        app.env.registerTimer("JobReceive")
        self.app = app

        # Create the job handlers.
        job_handlers = {
                JOB_LOAD: LoadJobHandler(app, self.ctx),
                JOB_RENDER_FIRST: RenderFirstSubJobHandler(app, self.ctx),
                JOB_BAKE: BakeJobHandler(app, self.ctx)}
        for jt, jh in job_handlers.items():
            app.env.registerTimer(type(jh).__name__)
        self.job_handlers = job_handlers

        app.env.stepTimerSince("BakeWorkerInit", self.work_start_time)

    def process(self, job):
        handler = self.job_handlers[job.job_type]
        with self.app.env.timerScope(type(handler).__name__):
            return handler.handleJob(job)

    def getReport(self):
        self.app.env.stepTimerSince("BakeWorker_%d_Total" % self.wid,
                                    self.work_start_time)
        return {
                'type': 'timers',
                'data': self.app.env._timers}


JOB_LOAD, JOB_RENDER_FIRST, JOB_BAKE = range(0, 3)


class BakeWorkerJob(object):
    def __init__(self, job_type, payload):
        self.job_type = job_type
        self.payload = payload


class JobHandler(object):
    def __init__(self, app, ctx):
        self.app = app
        self.ctx = ctx

    def handleJob(self, job):
        raise NotImplementedError()


def _get_errors(ex):
    errors = []
    while ex is not None:
        errors.append(str(ex))
        ex = ex.__cause__
    return errors


class PageFactoryInfo(object):
    def __init__(self, fac):
        self.source_name = fac.source.name
        self.rel_path = fac.rel_path
        self.metadata = fac.metadata

    def build(self, app):
        source = app.getSource(self.source_name)
        return PageFactory(source, self.rel_path, self.metadata)


class LoadJobPayload(object):
    def __init__(self, fac):
        self.factory_info = PageFactoryInfo(fac)


class LoadJobResult(object):
    def __init__(self, source_name, path):
        self.source_name = source_name
        self.path = path
        self.config = None
        self.errors = None


class RenderFirstSubJobPayload(object):
    def __init__(self, fac):
        self.factory_info = PageFactoryInfo(fac)


class RenderFirstSubJobResult(object):
    def __init__(self, path):
        self.path = path
        self.errors = None


class BakeJobPayload(object):
    def __init__(self, fac, route_metadata, previous_entry,
                 dirty_source_names, tax_info=None):
        self.factory_info = PageFactoryInfo(fac)
        self.route_metadata = route_metadata
        self.previous_entry = previous_entry
        self.dirty_source_names = dirty_source_names
        self.taxonomy_info = tax_info


class BakeJobResult(object):
    def __init__(self, path, tax_info=None):
        self.path = path
        self.taxonomy_info = tax_info
        self.sub_entries = None
        self.errors = None


class LoadJobHandler(JobHandler):
    def handleJob(self, job):
        # Just make sure the page has been cached.
        fac = job.payload.factory_info.build(self.app)
        logger.debug("Loading page: %s" % fac.ref_spec)
        result = LoadJobResult(fac.source.name, fac.path)
        try:
            page = fac.buildPage()
            page._load()
            result.config = page.config.getAll()
        except Exception as ex:
            logger.debug("Got loading error. Sending it to master.")
            result.errors = _get_errors(ex)
            if self.ctx.debug:
                logger.exception(ex)
        return result


class RenderFirstSubJobHandler(JobHandler):
    def handleJob(self, job):
        # Render the segments for the first sub-page of this page.
        fac = job.payload.factory_info.build(self.app)

        # These things should be OK as they're checked upstream by the baker.
        route = self.app.getRoute(fac.source.name, fac.metadata,
                                  skip_taxonomies=True)
        assert route is not None

        page = fac.buildPage()
        route_metadata = create_route_metadata(page)
        qp = QualifiedPage(page, route, route_metadata)
        ctx = PageRenderingContext(qp)

        result = RenderFirstSubJobResult(fac.path)
        logger.debug("Preparing page: %s" % fac.ref_spec)
        try:
            render_page_segments(ctx)
        except Exception as ex:
            logger.debug("Got rendering error. Sending it to master.")
            result.errors = _get_errors(ex)
            if self.ctx.debug:
                logger.exception(ex)
        return result


class BakeJobHandler(JobHandler):
    def __init__(self, app, ctx):
        super(BakeJobHandler, self).__init__(app, ctx)
        self.page_baker = PageBaker(app, ctx.out_dir, ctx.force)

    def handleJob(self, job):
        # Actually bake the page and all its sub-pages to the output folder.
        fac = job.payload.factory_info.build(self.app)

        route_metadata = job.payload.route_metadata
        tax_info = job.payload.taxonomy_info
        if tax_info is not None:
            route = self.app.getTaxonomyRoute(tax_info.taxonomy_name,
                                              tax_info.source_name)
        else:
            route = self.app.getRoute(fac.source.name, route_metadata,
                                      skip_taxonomies=True)
        assert route is not None

        page = fac.buildPage()
        qp = QualifiedPage(page, route, route_metadata)

        result = BakeJobResult(fac.path, tax_info)
        previous_entry = job.payload.previous_entry
        dirty_source_names = job.payload.dirty_source_names
        logger.debug("Baking page: %s" % fac.ref_spec)
        try:
            sub_entries = self.page_baker.bake(
                    qp, previous_entry, dirty_source_names, tax_info)
            result.sub_entries = sub_entries

        except BakingError as ex:
            logger.debug("Got baking error. Sending it to master.")
            result.errors = _get_errors(ex)
            if self.ctx.debug:
                logger.exception(ex)

        return result

