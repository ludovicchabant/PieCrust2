import logging
from piecrust.pipelines.base import ContentPipeline
from piecrust.pipelines._pagebaker import PageBaker
from piecrust.pipelines._pagerecords import PagePipelineRecordEntry
from piecrust.rendering import (
    RenderingContext, render_page_segments)
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


class PagePipeline(ContentPipeline):
    PIPELINE_NAME = 'page'
    RECORD_ENTRY_CLASS = PagePipelineRecordEntry

    def __init__(self, source, ppctx):
        super().__init__(source, ppctx)
        self._pagebaker = None
        self._stats = source.app.env.stats

    def initialize(self):
        stats = self.app.env.stats
        stats.registerCounter('SourceUseAbortions', raise_if_registered=False)

        self._pagebaker = PageBaker(self.app,
                                    self.ctx.out_dir,
                                    force=self.ctx.force)
        self._pagebaker.startWriterQueue()

    def mergeRecordEntry(self, record_entry, ctx):
        existing = ctx.record.getEntry(record_entry.item_spec)
        existing.errors += record_entry.errors
        existing.flags |= record_entry.flags
        existing.subs = record_entry.subs

    def run(self, job, ctx, result):
        pass_name = job.data.get('pass', 0)
        if pass_name == 0:
            self._renderSegmentsOrPostpone(job.content_item, ctx, result)
        elif pass_name == 1:
            self._fullRender(job.content_item, ctx, result)

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

    def _renderSegmentsOrPostpone(self, content_item, ctx, result):
        # Here our job is to render the page's segments so that they're
        # cached in memory and on disk... unless we detect that the page
        # is using some other sources, in which case we abort and we'll try
        # again on the second pass.
        logger.debug("Rendering segments for: %s" % content_item.spec)
        record_entry = result.record_entry
        stats = self.app.env.stats

        page = self.app.getPage(self.source, content_item)
        record_entry.config = page.config.getAll()

        rdrctx = RenderingContext(page)
        self.app.env.abort_source_use = True
        try:
            render_page_segments(rdrctx)
        except AbortedSourceUseError:
            logger.debug("Page was aborted for using source: %s" %
                         content_item.spec)
            stats.stepCounter("SourceUseAbortions")
        finally:
            self.app.env.abort_source_use = False

        result.next_pass_job = self.createJob(content_item)
        result.next_pass_job.data.update({
            'pass': 1,
            'record_entry': record_entry
        })

    def _fullRender(self, content_item, ctx, result):
        logger.debug("Full render for: %s" % content_item.spec)
        page = self.app.getPage(self.source, content_item)
        prev_entry = ctx.previous_entry
        cur_entry = result.record_entry
        self._pagebaker.bake(page, prev_entry, cur_entry, [])
