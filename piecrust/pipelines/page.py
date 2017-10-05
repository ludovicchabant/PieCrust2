import logging
from piecrust.pipelines.base import ContentPipeline
from piecrust.pipelines._pagebaker import PageBaker
from piecrust.pipelines._pagerecords import PagePipelineRecordEntry
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


class PagePipeline(ContentPipeline):
    PIPELINE_NAME = 'page'
    RECORD_ENTRY_CLASS = PagePipelineRecordEntry

    def __init__(self, source, ppctx):
        super().__init__(source, ppctx)
        self._pagebaker = None
        self._stats = source.app.env.stats
        self._draft_setting = self.app.config['baker/no_bake_setting']

    def initialize(self):
        stats = self.app.env.stats
        stats.registerCounter('SourceUseAbortions', raise_if_registered=False)
        stats.registerManifest('SourceUseAbortions', raise_if_registered=False)

        self._pagebaker = PageBaker(self.app,
                                    self.ctx.out_dir,
                                    force=self.ctx.force)
        self._pagebaker.startWriterQueue()

    def createJobs(self, ctx):
        used_paths = {}
        for rec in ctx.record_histories.current.records:
            src_name = rec.name.split('@')[0]
            for e in rec.getEntries():
                paths = e.getAllOutputPaths()
                if paths is not None:
                    for p in paths:
                        used_paths[p] = (src_name, e)

        jobs = []
        route = self.source.route
        pretty_urls = self.app.config.get('site/pretty_urls')
        record = ctx.record_histories.current.getRecord(self.record_name)

        for item in self.source.getAllContents():
            route_params = item.metadata['route_params']
            uri = route.getUri(route_params)
            path = self._pagebaker.getOutputPath(uri, pretty_urls)
            override = used_paths.get(path)
            if override is not None:
                override_source_name, override_entry = override
                override_source = self.app.getSource(override_source_name)
                if override_source.config['realm'] == \
                        self.source.config['realm']:
                    logger.error(
                        "Page '%s' would get baked to '%s' "
                        "but is overriden by '%s'." %
                        (item.spec, path, override_entry.item_spec))
                else:
                    logger.debug(
                        "Page '%s' would get baked to '%s' "
                        "but is overriden by '%s'." %
                        (item.spec, path, override_entry.item_spec))

                entry = PagePipelineRecordEntry()
                entry.item_spec = item.spec
                entry.flags |= PagePipelineRecordEntry.FLAG_OVERRIDEN
                record.addEntry(entry)

                continue

            jobs.append(self.createJob(item))

        if len(jobs) > 0:
            return jobs
        return None

    def mergeRecordEntry(self, record_entry, ctx):
        existing = ctx.record.getEntry(record_entry.item_spec)
        existing.errors += record_entry.errors
        existing.flags |= record_entry.flags
        existing.subs = record_entry.subs

    def run(self, job, ctx, result):
        step_num = job.step_num
        if step_num == 0:
            self._loadPage(job.content_item, ctx, result)
        elif step_num == 1:
            self._renderOrPostpone(job.content_item, ctx, result)
        elif step_num == 2:
            self._renderAlways(job.content_item, ctx, result)

    def getDeletions(self, ctx):
        for prev, cur in ctx.record_history.diffs:
            if prev and not cur:
                for sub in prev.subs:
                    yield (sub.out_path, 'previous source file was removed')
            elif prev and cur:
                prev_out_paths = [o.out_path for o in prev.subs]
                cur_out_paths = [o.out_path for o in cur.subs]
                diff = set(prev_out_paths) - set(cur_out_paths)
                for p in diff:
                    yield (p, 'source file changed outputs')

    def collapseRecords(self, ctx):
        pass

    def shutdown(self):
        self._pagebaker.stopWriterQueue()

    def _loadPage(self, content_item, ctx, result):
        logger.debug("Loading page: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        record_entry = result.record_entry
        record_entry.config = page.config.getAll()
        record_entry.timestamp = page.datetime.timestamp()

        if not page.config.get(self._draft_setting):
            result.next_step_job = self.createJob(content_item)
        else:
            record_entry.flags |= PagePipelineRecordEntry.FLAG_IS_DRAFT

    def _renderOrPostpone(self, content_item, ctx, result):
        # Here our job is to render the page's segments so that they're
        # cached in memory and on disk... unless we detect that the page
        # is using some other sources, in which case we abort and we'll try
        # again on the second pass.
        logger.debug("Conditional render for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        prev_entry = ctx.previous_entry
        cur_entry = result.record_entry
        self.app.env.abort_source_use = True
        try:
            self._pagebaker.bake(page, prev_entry, cur_entry)
        except AbortedSourceUseError:
            logger.debug("Page was aborted for using source: %s" %
                         content_item.spec)
            self.app.env.stats.stepCounter("SourceUseAbortions")
            self.app.env.stats.addManifestEntry("SourceUseAbortions",
                                                content_item.spec)
            result.next_step_job = self.createJob(content_item)
        finally:
            self.app.env.abort_source_use = False

    def _renderAlways(self, content_item, ctx, result):
        logger.debug("Full render for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        prev_entry = ctx.previous_entry
        cur_entry = result.record_entry
        self._pagebaker.bake(page, prev_entry, cur_entry)
