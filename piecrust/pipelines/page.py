import time
import logging
from piecrust.pipelines.base import (
    ContentPipeline, create_job, content_item_from_job)
from piecrust.pipelines._pagebaker import PageBaker, get_output_path
from piecrust.pipelines._pagerecords import (
    PagePipelineRecordEntry,
    add_page_job_result, merge_job_result_into_record_entry)
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


class PagePipeline(ContentPipeline):
    PIPELINE_NAME = 'page'
    RECORD_ENTRY_CLASS = PagePipelineRecordEntry
    PASS_NUM = [0, 1]

    def __init__(self, source, ppctx):
        super().__init__(source, ppctx)
        self._pagebaker = None
        self._stats = source.app.env.stats
        self._draft_setting = self.app.config['baker/no_bake_setting']

    def initialize(self):
        stats = self._stats
        stats.registerCounter('SourceUseAbortions', raise_if_registered=False)
        stats.registerManifest('SourceUseAbortions', raise_if_registered=False)

        self._pagebaker = PageBaker(self.app,
                                    self.ctx.out_dir,
                                    force=self.ctx.force)
        self._pagebaker.startWriterQueue()

    def loadAllContents(self):
        # Here we load all the pages in the source, making sure they all
        # have a valid cache for their configuration and contents.
        # We also create the record entries while we're at it.
        source = self.source
        page_fac = self.app.getPage
        record_fac = self.createRecordEntry
        for item in source.getAllContents():
            page = page_fac(source, item)

            cur_entry = record_fac(item.spec)
            cur_entry.config = page.config.getAll()
            cur_entry.route_params = item.metadata['route_params']
            cur_entry.timestamp = page.datetime.timestamp()

            if page.config.get(self._draft_setting):
                cur_entry.flags |= PagePipelineRecordEntry.FLAG_IS_DRAFT

            yield cur_entry

    def createJobs(self, ctx):
        if ctx.pass_num == 0:
            return self._createFirstPassJobs(ctx)
        return self._createSecondPassJobs(ctx)

    def _createFirstPassJobs(self, ctx):
        jobs = []

        app = self.app
        out_dir = self.ctx.out_dir
        uri_getter = self.source.route.getUri
        pretty_urls = app.config.get('site/pretty_urls')

        used_paths = _get_used_paths_from_records(
            ctx.record_histories.current.records)
        history = ctx.record_histories.getHistory(ctx.record_name).copy()
        history.build()

        record = ctx.current_record
        record.user_data['dirty_source_names'] = set()

        for prev, cur in history.diffs:
            # Ignore pages that disappeared since last bake.
            if cur is None:
                continue

            # Skip draft pages.
            if cur.flags & PagePipelineRecordEntry.FLAG_IS_DRAFT:
                continue

            # Skip pages that are known to use other sources... we'll
            # schedule them in the second pass.
            if prev and prev.getAllUsedSourceNames():
                continue

            # Check if this item has been overriden by a previous pipeline
            # run... for instance, we could be the pipeline for a "theme pages"
            # source, and some of our pages have been overriden by a user
            # page that writes out to the same URL.
            uri = uri_getter(cur.route_params)
            path = get_output_path(app, out_dir, uri, pretty_urls)

            override = used_paths.get(path)
            if override is not None:
                override_source_name, override_entry = override
                override_source = app.getSource(override_source_name)
                if override_source.config['realm'] == \
                        self.source.config['realm']:
                    logger.error(
                        "Page '%s' would get baked to '%s' "
                        "but is overriden by '%s'." %
                        (enrty.item_spec, path, override_entry.item_spec))
                else:
                    logger.debug(
                        "Page '%s' would get baked to '%s' "
                        "but is overriden by '%s'." %
                        (cur.item_spec, path, override_entry.item_spec))

                cur.flags |= PagePipelineRecordEntry.FLAG_OVERRIDEN
                continue

            # Nope, all good, let's create a job for this item.
            jobs.append(create_job(self, cur.item_spec))

        if len(jobs) > 0:
            return jobs
        return None

    def _createSecondPassJobs(self, ctx):
        # Get the list of all sources that had anything baked.
        dirty_source_names = set()
        all_records = ctx.record_histories.current.records
        for rec in all_records:
            rec_dsn = rec.user_data.get('dirty_source_names')
            if rec_dsn:
                dirty_source_names |= rec_dsn

        # Now look at the stuff we bake for our own source on the first pass.
        # For anything that wasn't baked (i.e. it was considered 'up to date')
        # we look at the records from last time, and if they say that some
        # page was using a source that is "dirty", then we force bake it.
        #
        # The common example for this is a blog index page which hasn't been
        # touched, but needs to be re-baked because someone added or edited
        # a post.
        jobs = []
        pass_num = ctx.pass_num
        history = ctx.record_histories.getHistory(ctx.record_name).copy()
        history.build()
        for prev, cur in history.diffs:
            if cur and cur.was_any_sub_baked:
                continue
            if prev and any(map(
                    lambda usn: usn in dirty_source_names,
                    prev.getAllUsedSourceNames())):
                jobs.append(create_job(self, prev.item_spec,
                                       pass_num=pass_num,
                                       force_bake=True))
        if len(jobs) > 0:
            return jobs
        return None

    def handleJobResult(self, result, ctx):
        existing = ctx.record_entry
        merge_job_result_into_record_entry(existing, result)
        if existing.was_any_sub_baked:
            ctx.record.user_data['dirty_source_names'].add(self.source.name)

    def run(self, job, ctx, result):
        pass_num = job.get('pass_num', 0)
        step_num = job.get('step_num', 0)
        if pass_num == 0:
            if step_num == 0:
                self._renderOrPostpone(job, ctx, result)
            elif step_num == 1:
                self._renderAlways(job, ctx, result)
        elif pass_num == 1:
            self._renderAlways(job, ctx, result)

    def getDeletions(self, ctx):
        for prev, cur in ctx.record_history.diffs:
            if prev and not cur:
                for sub in prev.subs:
                    yield (sub['out_path'], 'previous source file was removed')
            elif prev and cur:
                prev_out_paths = [o['out_path'] for o in prev.subs]
                cur_out_paths = [o['out_path'] for o in cur.subs]
                diff = set(prev_out_paths) - set(cur_out_paths)
                for p in diff:
                    yield (p, 'source file changed outputs')

    def collapseRecords(self, ctx):
        pass

    def shutdown(self):
        self._pagebaker.stopWriterQueue()

    def _renderOrPostpone(self, job, ctx, result):
        # Here our job is to render the page's segments so that they're
        # cached in memory and on disk... unless we detect that the page
        # is using some other sources, in which case we abort and we'll try
        # again on the second pass.
        content_item = content_item_from_job(self, job)
        logger.debug("Conditional render for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        if page.config.get(self._draft_setting):
            return

        prev_entry = ctx.previous_entry

        env = self.app.env
        env.abort_source_use = True
        add_page_job_result(result)
        try:
            rdr_subs = self._pagebaker.bake(page, prev_entry)
            result['subs'] = rdr_subs
        except AbortedSourceUseError:
            logger.debug("Page was aborted for using source: %s" %
                         content_item.spec)
            result['flags'] |= \
                PagePipelineRecordEntry.FLAG_ABORTED_FOR_SOURCE_USE
            env.stats.stepCounter("SourceUseAbortions")
            env.stats.addManifestEntry("SourceUseAbortions", content_item.spec)
            result['next_step_job'] = create_job(self, content_item.spec)
        finally:
            env.abort_source_use = False

    def _renderAlways(self, job, ctx, result):
        content_item = content_item_from_job(self, job)
        logger.debug("Full render for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        prev_entry = ctx.previous_entry
        rdr_subs = self._pagebaker.bake(page, prev_entry,
                                        force=job.get('force_bake'))

        add_page_job_result(result)
        result['subs'] = rdr_subs

def _get_used_paths_from_records(records):
    used_paths = {}
    for rec in records:
        src_name = rec.name.split('@')[0]
        for e in rec.getEntries():
            paths = e.getAllOutputPaths()
            if paths is not None:
                for p in paths:
                    used_paths[p] = (src_name, e)
    return used_paths
