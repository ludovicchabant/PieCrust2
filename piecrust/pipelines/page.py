import copy
import logging
from piecrust.pipelines.base import (
    ContentPipeline, create_job, content_item_from_job)
from piecrust.pipelines._pagebaker import PageBaker, get_output_path
from piecrust.pipelines._pagerecords import (
    PagePipelineRecordEntry, SubPageFlags)
from piecrust.rendering import RenderingContext, render_page_segments
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
            ctx.current_record.user_data['dirty_source_names'] = set()
            return self._createLoadJobs(ctx), "load"
        if pass_num == 1:
            return self._createSegmentJobs(ctx), "render"
        if pass_num == 2:
            return self._createLayoutJobs(ctx), "layout"
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

    def _createSegmentJobs(self, ctx):
        jobs = []

        app = self.app
        pass_num = ctx.pass_num
        out_dir = self.ctx.out_dir
        uri_getter = self.source.route.getUri
        pretty_urls = app.config.get('site/pretty_urls')

        history = ctx.record_histories.getHistory(ctx.record_name).copy()
        history.build()

        cur_rec_used_paths = {}
        history.current.user_data['used_paths'] = cur_rec_used_paths
        all_records = ctx.record_histories.current.records

        for prev, cur in history.diffs:
            # Ignore pages that disappeared since last bake.
            if cur is None:
                continue

            # Skip draft pages.
            if cur.hasFlag(PagePipelineRecordEntry.FLAG_IS_DRAFT):
                continue

            # Skip pages that haven't changed since last bake.
            if (prev and not cur.hasFlag(
                    PagePipelineRecordEntry.FLAG_SOURCE_MODIFIED)):
                continue

            # For pages that are known to use other sources in their own
            # content segments (we don't care about the layout yet), we
            # postpone them to the next pipeline pass immediately, because they
            # might need populated render caches for those sources' pages.
            if prev:
                usn1, _ = prev.getAllUsedSourceNames()
                if usn1:
                    logger.debug("Postponing: %s" % cur.item_spec)
                    cur.flags |= \
                        PagePipelineRecordEntry.FLAG_ABORTED_FOR_SOURCE_USE
                    continue

            # Check if this item has been overriden by a previous pipeline
            # run... for instance, we could be the pipeline for a "theme pages"
            # source, and some of our pages have been overriden by a user
            # page that writes out to the same URL.
            uri = uri_getter(cur.route_params)
            out_path = get_output_path(app, out_dir, uri, pretty_urls)
            override = _find_used_path_spec(all_records, out_path)
            if override is not None:
                override_source_name, override_entry_spec = override
                override_source = app.getSource(override_source_name)
                if override_source.config['realm'] == \
                        self.source.config['realm']:
                    logger.error(
                        "Page '%s' would get baked to '%s' "
                        "but is overriden by '%s'." %
                        (cur.item_spec, out_path, override_entry_spec))
                else:
                    logger.debug(
                        "Page '%s' would get baked to '%s' "
                        "but is overriden by '%s'." %
                        (cur.item_spec, out_path, override_entry_spec))

                cur.flags |= PagePipelineRecordEntry.FLAG_OVERRIDEN
                continue

            # Nope, all good, let's create a job for this item.
            cur.flags |= PagePipelineRecordEntry.FLAG_SEGMENTS_RENDERED
            cur_rec_used_paths[out_path] = cur.item_spec

            jobs.append(create_job(self, cur.item_spec,
                                   pass_num=pass_num))

        if len(jobs) > 0:
            return jobs
        return None

    def _createLayoutJobs(self, ctx):
        # Get the list of all sources that had anything baked.
        dirty_source_names = set()
        all_records = ctx.record_histories.current.records
        for rec in all_records:
            rec_dsn = rec.user_data.get('dirty_source_names')
            if rec_dsn:
                dirty_source_names |= rec_dsn

        jobs = []
        pass_num = ctx.pass_num
        history = ctx.record_histories.getHistory(ctx.record_name).copy()
        history.build()
        for prev, cur in history.diffs:
            if not cur or cur.hasFlag(PagePipelineRecordEntry.FLAG_OVERRIDEN):
                continue

            do_bake = False
            force_segments = False
            force_layout = False

            # Make sure we bake the layout for pages that got their segments
            # re-rendered.
            if cur.hasFlag(PagePipelineRecordEntry.FLAG_SEGMENTS_RENDERED):
                do_bake = True

            # Now look at the stuff we baked for our own source on the second
            # pass.  For anything that wasn't baked (i.e. it was considered 'up
            # to date') we look at the records from last time, and if they say
            # that some page was using a source that is "dirty", then we force
            # bake it.
            #
            # The common example for this is a blog index page which hasn't
            # been touched, but needs to be re-baked because someone added or
            # edited a post.
            if prev:
                usn1, usn2 = prev.getAllUsedSourceNames()
                force_segments = any(map(lambda u: u in dirty_source_names,
                                     usn1))
                force_layout = any(map(lambda u: u in dirty_source_names,
                                   usn2))

                if force_segments or force_layout:
                    # Yep, we need to force-rebake some aspect of this page.
                    do_bake = True

                elif not do_bake:
                    # This page uses other sources, but no source was dirty
                    # this time around (it was a null build, maybe). We
                    # don't have any work to do, but we need to carry over
                    # any information we have, otherwise the post bake step
                    # will think we need to delete last bake's outputs.
                    cur.subs = copy.deepcopy(prev.subs)
                    for cur_sub in cur.subs:
                        cur_sub['flags'] = \
                            SubPageFlags.FLAG_COLLAPSED_FROM_LAST_RUN

            if do_bake:
                jobs.append(create_job(self, cur.item_spec,
                                       pass_num=pass_num,
                                       force_segments=force_segments,
                                       force_layout=force_layout))

        if len(jobs) > 0:
            return jobs
        return None

    def handleJobResult(self, result, ctx):
        pass_num = ctx.pass_num

        if pass_num == 0:
            # Just went through a "load page" job. Let's create a record
            # entry with the information we got from the worker.
            new_entry = self.createRecordEntry(result['item_spec'])
            new_entry.flags = result['flags']
            new_entry.config = result['config']
            new_entry.route_params = result['route_params']
            new_entry.timestamp = result['timestamp']
            ctx.record.addEntry(new_entry)

            # If this page was modified, flag its entire source as "dirty",
            # so any pages using that source can be re-baked.
            if new_entry.flags & PagePipelineRecordEntry.FLAG_SOURCE_MODIFIED:
                ctx.record.user_data['dirty_source_names'].add(
                    self.source.name)

            # If this page is new

        elif pass_num == 1:
            # Just went through the "render segments" job.
            existing = ctx.record_entry
            existing.flags |= result.get('flags',
                                         PagePipelineRecordEntry.FLAG_NONE)

        else:
            # Update the entry with the new information.
            existing = ctx.record_entry
            existing.flags |= result.get('flags',
                                         PagePipelineRecordEntry.FLAG_NONE)
            existing.errors += result.get('errors', [])
            existing.subs += result.get('subs', [])

    def run(self, job, ctx, result):
        pass_num = job.get('pass_num', 0)

        if pass_num == 0:
            return self._loadPage(job, ctx, result)

        elif pass_num == 1:
            return self._renderSegments(job, ctx, result)

        elif pass_num >= 2:
            return self._renderLayout(job, ctx, result)

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

    def _renderSegments(self, job, ctx, result):
        # Here our job is to render the page's segments so that they're
        # cached in memory and on disk... unless we detect that the page
        # is using some other sources, in which case we abort and we'll try
        # again on the second pass.
        content_item = content_item_from_job(self, job)
        logger.debug("Render segments for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        if page.config.get(self._draft_setting):
            raise Exception("Shouldn't have a draft page in a render job!")

        env = self.app.env
        env.abort_source_use = True
        try:
            rdr_ctx = RenderingContext(page)
            render_page_segments(rdr_ctx)
        except AbortedSourceUseError:
            logger.debug("Page was aborted for using source: %s" %
                         content_item.spec)
            result['flags'] = \
                PagePipelineRecordEntry.FLAG_ABORTED_FOR_SOURCE_USE
            env.stats.stepCounter("SourceUseAbortions")
            env.stats.addManifestEntry("SourceUseAbortions", content_item.spec)
        finally:
            env.abort_source_use = False

    def _renderLayout(self, job, ctx, result):
        content_item = content_item_from_job(self, job)
        logger.debug("Render layout for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        prev_entry = ctx.previous_entry
        rdr_subs = self._pagebaker.bake(
            page, prev_entry,
            force_segments=job.get('force_segments'),
            force_layout=job.get('force_layout'))
        result['subs'] = rdr_subs


def _find_used_path_spec(records, path):
    for rec in records:
        up = rec.user_data.get('used_paths')
        if up is not None:
            entry_spec = up.get(path)
            if entry_spec is not None:
                src_name = rec.name.split('@')[0]
                return (src_name, entry_spec)
    return None
