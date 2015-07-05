import re
import os.path
import time
import logging
from piecrust.app import PieCrust
from piecrust.processing.base import PipelineContext
from piecrust.processing.records import (
        FLAG_NONE, FLAG_PREPARED, FLAG_PROCESSED,
        FLAG_BYPASSED_STRUCTURED_PROCESSING)
from piecrust.processing.tree import (
        ProcessingTreeBuilder, ProcessingTreeRunner,
        ProcessingTreeError, ProcessorError,
        get_node_name_tree, print_node,
        STATE_DIRTY)
from piecrust.workerpool import IWorker


logger = logging.getLogger(__name__)


split_processor_names_re = re.compile(r'[ ,]+')
re_ansicolors = re.compile('\033\\[\d+m')


class ProcessingWorkerContext(object):
    def __init__(self, root_dir, out_dir, tmp_dir,
                 force=False, debug=False):
        self.root_dir = root_dir
        self.out_dir = out_dir
        self.tmp_dir = tmp_dir
        self.force = force
        self.debug = debug
        self.is_profiling = False
        self.enabled_processors = None
        self.additional_processors = None


class ProcessingWorkerJob(object):
    def __init__(self, base_dir, mount_info, path, *, force=False):
        self.base_dir = base_dir
        self.mount_info = mount_info
        self.path = path
        self.force = force


class ProcessingWorkerResult(object):
    def __init__(self, path):
        self.path = path
        self.flags = FLAG_NONE
        self.proc_tree = None
        self.rel_outputs = None
        self.errors = None


class ProcessingWorker(IWorker):
    def __init__(self, ctx):
        self.ctx = ctx
        self.work_start_time = time.perf_counter()

    def initialize(self):
        # Create the app local to this worker.
        app = PieCrust(self.ctx.root_dir, debug=self.ctx.debug)
        app.env.registerTimer("PipelineWorker_%d_Total" % self.wid)
        app.env.registerTimer("PipelineWorkerInit")
        app.env.registerTimer("JobReceive")
        app.env.registerTimer('BuildProcessingTree')
        app.env.registerTimer('RunProcessingTree')
        self.app = app

        processors = app.plugin_loader.getProcessors()
        if self.ctx.enabled_processors:
            logger.debug("Filtering processors to: %s" %
                         self.ctx.enabled_processors)
            processors = get_filtered_processors(processors,
                                                 self.ctx.enabled_processors)
        if self.ctx.additional_processors:
            logger.debug("Adding %s additional processors." %
                         len(self.ctx.additional_processors))
            for proc in self.ctx.additional_processors:
                app.env.registerTimer(proc.__class__.__name__)
                proc.initialize(app)
                processors.append(proc)
        self.processors = processors

        # Invoke pre-processors.
        pipeline_ctx = PipelineContext(self.wid, self.app, self.ctx.out_dir,
                                       self.ctx.tmp_dir, self.ctx.force)
        for proc in processors:
            proc.onPipelineStart(pipeline_ctx)

        # Sort our processors again in case the pre-process step involved
        # patching the processors with some new ones.
        processors.sort(key=lambda p: p.priority)

        app.env.stepTimerSince("PipelineWorkerInit", self.work_start_time)

    def process(self, job):
        result = ProcessingWorkerResult(job.path)

        processors = get_filtered_processors(
                self.processors, job.mount_info['processors'])

        # Build the processing tree for this job.
        rel_path = os.path.relpath(job.path, job.base_dir)
        try:
            with self.app.env.timerScope('BuildProcessingTree'):
                builder = ProcessingTreeBuilder(processors)
                tree_root = builder.build(rel_path)
                result.flags |= FLAG_PREPARED
        except ProcessingTreeError as ex:
            result.errors = _get_errors(ex)
            return result

        # Prepare and run the tree.
        print_node(tree_root, recursive=True)
        leaves = tree_root.getLeaves()
        result.rel_outputs = [l.path for l in leaves]
        result.proc_tree = get_node_name_tree(tree_root)
        if tree_root.getProcessor().is_bypassing_structured_processing:
            result.flags |= FLAG_BYPASSED_STRUCTURED_PROCESSING

        if job.force:
            tree_root.setState(STATE_DIRTY, True)

        try:
            with self.app.env.timerScope('RunProcessingTree'):
                runner = ProcessingTreeRunner(
                        job.base_dir, self.ctx.tmp_dir, self.ctx.out_dir)
                if runner.processSubTree(tree_root):
                    result.flags |= FLAG_PROCESSED
        except ProcessingTreeError as ex:
            if isinstance(ex, ProcessorError):
                ex = ex.__cause__
            # Need to strip out colored errors from external processes.
            result.errors = _get_errors(ex, strip_colors=True)

        return result

    def getReport(self):
        # Invoke post-processors.
        pipeline_ctx = PipelineContext(self.wid, self.app, self.ctx.out_dir,
                                       self.ctx.tmp_dir, self.ctx.force)
        for proc in self.processors:
            proc.onPipelineEnd(pipeline_ctx)

        self.app.env.stepTimerSince("PipelineWorker_%d_Total" % self.wid,
                                    self.work_start_time)
        return {
                'type': 'timers',
                'data': self.app.env._timers}


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


def _get_errors(ex, strip_colors=False):
    errors = []
    while ex is not None:
        msg = str(ex)
        if strip_colors:
            msg = re_ansicolors.sub('', msg)
        errors.append(msg)
        ex = ex.__cause__
    return errors

