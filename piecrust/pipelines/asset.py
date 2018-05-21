import os
import os.path
import re
import logging
from piecrust.pipelines._procrecords import (
    AssetPipelineRecordEntry,
    add_asset_job_result, merge_job_result_into_record_entry)
from piecrust.pipelines._proctree import (
    ProcessingTreeBuilder, ProcessingTreeRunner,
    get_node_name_tree, print_node,
    STATE_DIRTY)
from piecrust.pipelines.base import ContentPipeline
from piecrust.processing.base import ProcessorContext
from piecrust.sources.fs import FSContentSourceBase


logger = logging.getLogger(__name__)


class AssetPipeline(ContentPipeline):
    PIPELINE_NAME = 'asset'
    RECORD_ENTRY_CLASS = AssetPipelineRecordEntry

    def __init__(self, source, ppctx):
        if not isinstance(source, FSContentSourceBase):
            raise Exception(
                "The asset pipeline only support file-system sources.")

        super().__init__(source, ppctx)
        self._ignore_patterns = []
        self._processors = None
        self._base_dir = source.fs_endpoint_path

    def initialize(self):
        # Get the list of processors for this run.
        processors = self.app.plugin_loader.getProcessors()
        for flt in [
                self.app.config.get('pipelines/asset/processors'),
                self.source.config.get('processors')]:
            if flt is not None:
                processors = get_filtered_processors(processors, flt)
        logger.debug("Filtering processors to: %s" % processors)

        # Invoke pre-processors.
        proc_ctx = ProcessorContext(self)
        for proc in processors:
            proc.onPipelineStart(proc_ctx)

        # Add any extra processors registered in the `onPipelineStart` step.
        processors += proc_ctx.extra_processors

        # Sort our processors by priority.
        processors.sort(key=lambda p: p.priority)

        # Ok, that's the list of processors for this run.
        self._processors = processors

        # Pre-processors can define additional ignore patterns so let's
        # add them to what we had already.
        ignores = self.app.config.get('pipelines/asset/ignore', [])
        ignores += proc_ctx.ignore_patterns
        self._ignore_patterns += make_re(ignores)

        # Register timers.
        stats = self.app.env.stats
        stats.registerTimer('BuildProcessingTree', raise_if_registered=False)
        stats.registerTimer('RunProcessingTree', raise_if_registered=False)

    def run(self, job, ctx, result):
        # Create the result stuff.
        item_spec = job['job_spec'][1]
        add_asset_job_result(result)
        result['item_spec'] = item_spec

        # See if we need to ignore this item.
        rel_path = os.path.relpath(item_spec, self._base_dir)
        if re_matchany(rel_path, self._ignore_patterns):
            return

        # Build the processing tree for this job.
        stats = self.app.env.stats
        with stats.timerScope('BuildProcessingTree'):
            builder = ProcessingTreeBuilder(self._processors)
            tree_root = builder.build(rel_path)
            result['flags'] |= AssetPipelineRecordEntry.FLAG_PREPARED

        # Prepare and run the tree.
        out_dir = self.ctx.out_dir
        print_node(tree_root, recursive=True)
        leaves = tree_root.getLeaves()
        result['out_paths'] = [os.path.join(out_dir, l.path)
                               for l in leaves]
        result['proc_tree'] = get_node_name_tree(tree_root)
        if tree_root.getProcessor().is_bypassing_structured_processing:
            result['flags'] |= (
                AssetPipelineRecordEntry.FLAG_BYPASSED_STRUCTURED_PROCESSING)

        if self.ctx.force:
            tree_root.setState(STATE_DIRTY, True)

        with stats.timerScope('RunProcessingTree'):
            runner = ProcessingTreeRunner(
                self._base_dir, self.tmp_dir, out_dir)
            if runner.processSubTree(tree_root):
                result['flags'] |= (
                    AssetPipelineRecordEntry.FLAG_PROCESSED)

    def handleJobResult(self, result, ctx):
        entry = self.createRecordEntry(result['item_spec'])
        merge_job_result_into_record_entry(entry, result)
        ctx.record.addEntry(entry)

    def getDeletions(self, ctx):
        for prev, cur in ctx.record_history.diffs:
            if prev and not cur:
                for p in prev.out_paths:
                    yield (p, 'previous asset was removed')
            elif prev and cur and cur.was_processed_successfully:
                diff = set(prev.out_paths) - set(cur.out_paths)
                for p in diff:
                    yield (p, 'asset changed outputs')

    def collapseRecords(self, ctx):
        for prev, cur in ctx.record_history.diffs:
            if prev and cur and not cur.was_processed:
                # This asset wasn't processed, so the information from
                # last time is still valid.
                cur.flags = (
                    (prev.flags & ~AssetPipelineRecordEntry.FLAG_PROCESSED) |
                    AssetPipelineRecordEntry.FLAG_COLLAPSED_FROM_LAST_RUN)
                cur.out_paths = list(prev.out_paths)
                cur.errors = list(prev.errors)

    def shutdown(self):
        # Invoke post-processors.
        proc_ctx = ProcessorContext(self)
        for proc in self._processors:
            proc.onPipelineEnd(proc_ctx)


split_processor_names_re = re.compile(r'[ ,]+')


def get_filtered_processors(processors, authorized_names):
    if not authorized_names or authorized_names == 'all':
        return processors

    if isinstance(authorized_names, str):
        authorized_names = split_processor_names_re.split(authorized_names)

    procs = []
    has_star = 'all' in authorized_names
    for p in processors:
        for name in authorized_names:
            if name == p.PROCESSOR_NAME:
                procs.append(p)
                break
            if name == ('-%s' % p.PROCESSOR_NAME):
                break
        else:
            if has_star:
                procs.append(p)
    return procs


def make_re(patterns):
    re_patterns = []
    for pat in patterns:
        if pat[0] == '/' and pat[-1] == '/' and len(pat) > 2:
            re_patterns.append(pat[1:-1])
        else:
            escaped_pat = (
                re.escape(pat)
                .replace(r'\*', r'[^/\\]*')
                .replace(r'\?', r'[^/\\]'))
            re_patterns.append(escaped_pat)
    return [re.compile(p) for p in re_patterns]


def re_matchany(rel_path, patterns):
    # skip patterns use a forward slash regardless of the platform.
    rel_path = rel_path.replace('\\', '/')
    for pattern in patterns:
        if pattern.search(rel_path):
            return True
    return False


re_ansicolors = re.compile('\033\\[\d+m')


def _get_errors(ex, strip_colors=False):
    errors = []
    while ex is not None:
        msg = str(ex)
        if strip_colors:
            msg = re_ansicolors.sub('', msg)
        errors.append(msg)
        ex = ex.__cause__
    return errors

