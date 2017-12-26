import copy
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
    PASS_NUM = [0, 1, 2]

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

    def createJobs(self, ctx):
        pass_num = ctx.pass_num
        if pass_num == 0:
            return self._createLoadJobs(ctx)
        if pass_num == 1:
            return self._createSecondPassJobs(ctx)
        if pass_num == 2:
            return self._createThirdPassJobs(ctx)
        raise Exception("Unexpected pipeline pass: %d" % pass_num)

    def _createLoadJobs(self, ctx):
        # Here we load all the pages in the source, making sure they all
        # have a valid cache for their configuration and contents.
        jobs = []
        for item in self.source.getAllContents():
            jobs.append(create_job(self, item.spec))
        if len(jobs) > 0:
            return jobs
        return None

    def _createSecondPassJobs(self, ctx):
        jobs = []

        app = self.app
        out_dir = self.ctx.out_dir
        uri_getter = self.source.route.getUri
        pretty_urls = app.config.get('site/pretty_urls')

        used_paths = _get_used_paths_from_records(
            ctx.record_histories.current.records)
        history = ctx.record_histories.getHistory(ctx.record_name).copy()
        history.build()

        pass_num = ctx.pass_num
        record = ctx.current_record
        record.user_data['dirty_source_names'] = set()

        for prev, cur in history.diffs:
            # Ignore pages that disappeared since last bake.
            if cur is None:
                continue

            # Skip draft pages.
            if cur.flags & PagePipelineRecordEntry.FLAG_IS_DRAFT:
                continue

            # For pages that are known to use other sources, we make a dummy
            # job that will effectively get directly passed on to the next
            # step.
            if prev:
                usn1, usn2 = prev.getAllUsedSourceNames()
                if usn1 or usn2:
                    jobs.append(create_job(self, cur.item_spec,
                                           pass_num=pass_num,
                                           uses_sources=True))
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
                        (cur.item_spec, path, override_entry.item_spec))
                else:
                    logger.debug(
                        "Page '%s' would get baked to '%s' "
                        "but is overriden by '%s'." %
                        (cur.item_spec, path, override_entry.item_spec))

                cur.flags |= PagePipelineRecordEntry.FLAG_OVERRIDEN
                continue

            # Nope, all good, let's create a job for this item.
            jobs.append(create_job(self, cur.item_spec,
                                   pass_num=pass_num))

        if len(jobs) > 0:
            return jobs
        return None

    def _createThirdPassJobs(self, ctx):
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
            if not cur:
                continue
            if cur.was_any_sub_baked:
                continue
            if prev:
                if any(map(
                        lambda usn: usn in dirty_source_names,
                        prev.getAllUsedSourceNames()[0])):
                    jobs.append(create_job(self, prev.item_spec,
                                           pass_num=pass_num,
                                           force_bake=True))
                else:
                    # This page uses other sources, but no source was dirty
                    # this time around (it was a null build, maybe). We
                    # don't have any work to do, but we need to carry over
                    # any information we have, otherwise the post bake step
                    # will think we need to delete last bake's outputs.
                    cur.subs = copy.deepcopy(prev.subs)

        if len(jobs) > 0:
            return jobs
        return None

    def handleJobResult(self, result, ctx):
        pass_num = ctx.pass_num
        step_num = ctx.step_num

        if pass_num == 0:
            # Just went through a "load page" job. Let's create a record
            # entry with the information we got from the worker.
            new_entry = self.createRecordEntry(result['item_spec'])
            new_entry.flags = result['flags']
            new_entry.config = result['config']
            new_entry.route_params = result['route_params']
            new_entry.timestamp = result['timestamp']
            ctx.record.addEntry(new_entry)
        else:
            # Update the entry with the new information.
            existing = ctx.record_entry
            if not result.get('postponed', False):
                merge_job_result_into_record_entry(existing, result)
            if existing.was_any_sub_baked:
                ctx.record.user_data['dirty_source_names'].add(self.source.name)

    def run(self, job, ctx, result):
        pass_num = job.get('pass_num', 0)
        step_num = job.get('step_num', 0)

        if pass_num == 0:
            if step_num == 0:
                return self._loadPage(job, ctx, result)

        elif pass_num == 1:
            if step_num == 0:
                return self._renderOrPostpone(job, ctx, result)
            elif step_num == 1:
                return self._renderAlways(job, ctx, result)

        elif pass_num == 2:
            if step_num == 0:
                return self._renderAlways(job, ctx, result)

        raise Exception("Unexpected pipeline pass/step: %d/%d" %
                        (pass_num, step_num))

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

    def _loadPage(self, job, ctx, result):
        content_item = content_item_from_job(self, job)
        page = self.app.getPage(self.source, content_item)

        result['flags'] = PagePipelineRecordEntry.FLAG_NONE
        result['config'] = page.config.getAll()
        result['route_params'] = content_item.metadata['route_params']
        result['timestamp'] = page.datetime.timestamp()

        if page.was_modified:
            result['flags'] |= PagePipelineRecordEntry.FLAG_SOURCE_MODIFIED
        if page.config.get(self._draft_setting):
            result['flags'] |= PagePipelineRecordEntry.FLAG_IS_DRAFT

    def _renderOrPostpone(self, job, ctx, result):
        # See if we should immediately kick this job off to the next step.
        if job.get('uses_sources', False):
            result['postponed'] = True
            result['next_step_job'] = create_job(self, job['job_spec'][1])
            return

        # Here our job is to render the page's segments so that they're
        # cached in memory and on disk... unless we detect that the page
        # is using some other sources, in which case we abort and we'll try
        # again on the second pass.
        content_item = content_item_from_job(self, job)
        logger.debug("Conditional render for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        if page.config.get(self._draft_setting):
            raise Exception("Shouldn't have a draft page in a render job!")

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
