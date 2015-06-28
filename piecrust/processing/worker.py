import os.path
import re
import time
import queue
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


logger = logging.getLogger(__name__)


split_processor_names_re = re.compile(r'[ ,]+')
re_ansicolors = re.compile('\033\\[\d+m')


def worker_func(wid, ctx):
    if ctx.is_profiling:
        try:
            import cProfile as profile
        except ImportError:
            import profile

        ctx.is_profiling = False
        profile.runctx('_real_worker_func(wid, ctx)',
                       globals(), locals(),
                       filename='PipelineWorker-%d.prof' % wid)
    else:
        _real_worker_func(wid, ctx)


def _real_worker_func(wid, ctx):
    logger.debug("Worker %d booting up..." % wid)
    w = ProcessingWorker(wid, ctx)
    w.run()


class ProcessingWorkerContext(object):
    def __init__(self, root_dir, out_dir, tmp_dir,
                 work_queue, results, abort_event,
                 force=False, debug=False):
        self.root_dir = root_dir
        self.out_dir = out_dir
        self.tmp_dir = tmp_dir
        self.work_queue = work_queue
        self.results = results
        self.abort_event = abort_event
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


class ProcessingWorker(object):
    def __init__(self, wid, ctx):
        self.wid = wid
        self.ctx = ctx

    def run(self):
        logger.debug("Worker %d initializing..." % self.wid)
        work_start_time = time.perf_counter()

        # Create the app local to this worker.
        app = PieCrust(self.ctx.root_dir, debug=self.ctx.debug)
        app.env.fs_cache_only_for_main_page = True
        app.env.registerTimer("PipelineWorker_%d_Total" % self.wid)
        app.env.registerTimer("PipelineWorkerInit")
        app.env.registerTimer("JobReceive")
        app.env.registerTimer('BuildProcessingTree')
        app.env.registerTimer('RunProcessingTree')

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

        # Invoke pre-processors.
        pipeline_ctx = PipelineContext(self.wid, app, self.ctx.out_dir,
                                       self.ctx.tmp_dir, self.ctx.force)
        for proc in processors:
            proc.onPipelineStart(pipeline_ctx)

        # Sort our processors again in case the pre-process step involved
        # patching the processors with some new ones.
        processors.sort(key=lambda p: p.priority)

        app.env.stepTimerSince("PipelineWorkerInit", work_start_time)

        aborted_with_exception = None
        while not self.ctx.abort_event.is_set():
            try:
                with app.env.timerScope('JobReceive'):
                    job = self.ctx.work_queue.get(True, 0.01)
            except queue.Empty:
                continue

            try:
                result = self._unsafeRun(app, processors, job)
                self.ctx.results.put_nowait(result)
            except Exception as ex:
                self.ctx.abort_event.set()
                aborted_with_exception = ex
                logger.error("[%d] Critical error, aborting." % self.wid)
                if self.ctx.debug:
                    logger.exception(ex)
                break
            finally:
                self.ctx.work_queue.task_done()

        if aborted_with_exception is not None:
            msgs = _get_errors(aborted_with_exception)
            self.ctx.results.put_nowait({'type': 'error', 'messages': msgs})

        # Invoke post-processors.
        for proc in processors:
            proc.onPipelineEnd(pipeline_ctx)

        app.env.stepTimerSince("PipelineWorker_%d_Total" % self.wid,
                               work_start_time)
        self.ctx.results.put_nowait({
                'type': 'timers', 'data': app.env._timers})

    def _unsafeRun(self, app, processors, job):
        result = ProcessingWorkerResult(job.path)

        processors = get_filtered_processors(
                processors, job.mount_info['processors'])

        # Build the processing tree for this job.
        rel_path = os.path.relpath(job.path, job.base_dir)
        try:
            with app.env.timerScope('BuildProcessingTree'):
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
            with app.env.timerScope('RunProcessingTree'):
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

