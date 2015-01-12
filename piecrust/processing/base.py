import re
import time
import shutil
import os.path
import logging
import hashlib
import threading
from queue import Queue, Empty
from piecrust.chefutil import format_timed
from piecrust.processing.records import (
        ProcessorPipelineRecordEntry, TransitionalProcessorPipelineRecord,
        FLAG_PROCESSED, FLAG_OVERRIDEN, FLAG_BYPASSED_STRUCTURED_PROCESSING)
from piecrust.processing.tree import (
        ProcessingTreeBuilder, ProcessingTreeRunner, ProcessingTreeError,
        STATE_DIRTY,
        print_node, get_node_name_tree)


logger = logging.getLogger(__name__)


PRIORITY_FIRST = -1
PRIORITY_NORMAL = 0
PRIORITY_LAST = 1


class Processor(object):
    PROCESSOR_NAME = None

    def __init__(self):
        self.priority = PRIORITY_NORMAL
        self.is_bypassing_structured_processing = False
        self.is_delegating_dependency_check = True

    def initialize(self, app):
        self.app = app

    def onPipelineStart(self, pipeline):
        pass

    def onPipelineEnd(self, pipeline):
        pass

    def matches(self, path):
        return False

    def getDependencies(self, path):
        return None

    def getOutputFilenames(self, filename):
        return None

    def process(self, path, out_dir):
        pass


class CopyFileProcessor(Processor):
    PROCESSOR_NAME = 'copy'

    def __init__(self):
        super(CopyFileProcessor, self).__init__()
        self.priority = PRIORITY_LAST

    def matches(self, path):
        return True

    def getOutputFilenames(self, filename):
        return [filename]

    def process(self, path, out_dir):
        out_path = os.path.join(out_dir, os.path.basename(path))
        logger.debug("Copying: %s -> %s" % (path, out_path))
        shutil.copyfile(path, out_path)
        return True


class SimpleFileProcessor(Processor):
    def __init__(self, extensions=None):
        super(SimpleFileProcessor, self).__init__()
        self.extensions = extensions or {}

    def matches(self, path):
        for ext in self.extensions:
            if path.endswith('.' + ext):
                return True
        return False

    def getOutputFilenames(self, filename):
        basename, ext = os.path.splitext(filename)
        ext = ext.lstrip('.')
        out_ext = self.extensions[ext]
        return ['%s.%s' % (basename, out_ext)]

    def process(self, path, out_dir):
        _, in_name = os.path.split(path)
        out_name = self.getOutputFilenames(in_name)[0]
        out_path = os.path.join(out_dir, out_name)
        return self._doProcess(path, out_path)

    def _doProcess(self, in_path, out_path):
        raise NotImplementedError()


class ProcessingContext(object):
    def __init__(self, base_dir, job_queue, record=None):
        self.base_dir = base_dir
        self.job_queue = job_queue
        self.record = record


class ProcessorPipeline(object):
    def __init__(self, app, mounts, out_dir, force=False,
            skip_patterns=None, force_patterns=None, num_workers=4):
        assert app and out_dir
        self.app = app
        self.mounts = mounts
        tmp_dir = app.cache_dir
        if not tmp_dir:
            import tempfile
            tmp_dir = os.path.join(tempfile.gettempdir(), 'piecrust')
        self.tmp_dir = os.path.join(tmp_dir, 'proc')
        self.out_dir = out_dir
        self.force = force
        self.skip_patterns = skip_patterns or []
        self.force_patterns = force_patterns or []
        self.processors = app.plugin_loader.getProcessors()
        self.num_workers = num_workers

        self.skip_patterns += ['_cache', '_counter',
                'theme_info.yml',
                '.DS_Store', 'Thumbs.db',
                '.git*', '.hg*', '.svn']

        self.skip_patterns = make_re(self.skip_patterns)
        self.force_patterns = make_re(self.force_patterns)

    def filterProcessors(self, authorized_names):
        self.processors = list(filter(
            lambda p: p.PROCESSOR_NAME in authorized_names,
            self.processors))

    def run(self, src_dir_or_file=None, *,
            new_only=False, delete=True,
            previous_record=None, save_record=True):
        # Invoke pre-processors.
        for proc in self.processors:
            proc.onPipelineStart(self)

        # Sort our processors again in case the pre-process step involved
        # patching the processors with some new ones.
        self.processors.sort(key=lambda p: p.priority)

        # Create the pipeline record.
        record = TransitionalProcessorPipelineRecord()
        record_cache = self.app.cache.getCache('proc')
        record_name = (
                hashlib.md5(self.out_dir.encode('utf8')).hexdigest() +
                '.record')
        if previous_record:
            record.setPrevious(previous_record)
        elif not self.force and record_cache.has(record_name):
            t = time.clock()
            record.loadPrevious(record_cache.getCachePath(record_name))
            logger.debug(format_timed(t, 'loaded previous bake record',
                         colored=False))
        logger.debug("Got %d entries in process record." %
                len(record.previous.entries))

        # Create the workers.
        pool = []
        queue = Queue()
        abort = threading.Event()
        pipeline_lock = threading.Lock()
        for i in range(self.num_workers):
            ctx = ProcessingWorkerContext(self, record,
                                          queue, abort, pipeline_lock)
            worker = ProcessingWorker(i, ctx)
            worker.start()
            pool.append(worker)

        if src_dir_or_file is not None:
            # Process only the given path.
            # Find out what mount point this is in.
            for path in self.mounts:
                if src_dir_or_file[:len(path)] == path:
                    base_dir = path
                    break
            else:
                raise Exception("Input path '%s' is not part of any known "
                                "mount point: %s" %
                                (src_dir_or_file, self.mounts))

            ctx = ProcessingContext(base_dir, queue, record)
            logger.debug("Initiating processing pipeline on: %s" % src_dir_or_file)
            if os.path.isdir(src_dir_or_file):
                self.processDirectory(ctx, src_dir_or_file, new_only)
            elif os.path.isfile(src_dir_or_file):
                self.processFile(ctx, src_dir_or_file, new_only)

        else:
            # Process everything.
            for path in self.mounts:
                ctx = ProcessingContext(path, queue, record)
                logger.debug("Initiating processing pipeline on: %s" % path)
                self.processDirectory(ctx, path, new_only)

        # Wait on all workers.
        for w in pool:
            w.join()
        if abort.is_set():
            raise Exception("Worker pool was aborted.")

        # Handle deletions.
        if delete and not new_only:
            for path, reason in record.getDeletions():
                logger.debug("Removing '%s': %s" % (path, reason))
                os.remove(path)
                logger.info('[delete] %s' % path)

        # Invoke post-processors.
        for proc in self.processors:
            proc.onPipelineEnd(self)

        # Finalize the process record.
        record.current.process_time = time.time()
        record.current.out_dir = self.out_dir
        record.collapseRecords()

        # Save the process record.
        if save_record:
            t = time.clock()
            record.saveCurrent(record_cache.getCachePath(record_name))
            logger.debug(format_timed(t, 'saved bake record', colored=False))

        return record.detach()

    def processDirectory(self, ctx, start_dir, new_only=False):
        for dirpath, dirnames, filenames in os.walk(start_dir):
            rel_dirpath = os.path.relpath(dirpath, start_dir)
            dirnames[:] = [d for d in dirnames
                    if not re_matchany(d, self.skip_patterns, rel_dirpath)]

            for filename in filenames:
                if re_matchany(filename, self.skip_patterns, rel_dirpath):
                    continue
                self.processFile(ctx, os.path.join(dirpath, filename),
                                 new_only)

    def processFile(self, ctx, path, new_only=False):
        logger.debug("Queuing: %s" % path)
        job = ProcessingWorkerJob(ctx.base_dir, path, new_only)
        ctx.job_queue.put_nowait(job)


class ProcessingWorkerContext(object):
    def __init__(self, pipeline, record,
            work_queue, abort_event, pipeline_lock):
        self.pipeline = pipeline
        self.record = record
        self.work_queue = work_queue
        self.abort_event = abort_event
        self.pipeline_lock = pipeline_lock


class ProcessingWorkerJob(object):
    def __init__(self, base_dir, path, new_only=False):
        self.base_dir = base_dir
        self.path = path
        self.new_only = new_only


class ProcessingWorker(threading.Thread):
    def __init__(self, wid, ctx):
        super(ProcessingWorker, self).__init__()
        self.wid = wid
        self.ctx = ctx

    def run(self):
        while(not self.ctx.abort_event.is_set()):
            try:
                job = self.ctx.work_queue.get(True, 0.1)
            except Empty:
                logger.debug("[%d] No more work... shutting down." % self.wid)
                break

            try:
                self._unsafeRun(job)
                logger.debug("[%d] Done with file." % self.wid)
                self.ctx.work_queue.task_done()
            except Exception as ex:
                self.ctx.abort_event.set()
                logger.error("[%d] Critical error, aborting." % self.wid)
                logger.exception(ex)
                break

    def _unsafeRun(self, job):
        start_time = time.clock()
        pipeline = self.ctx.pipeline
        record = self.ctx.record

        rel_path = os.path.relpath(job.path, job.base_dir)
        previous_entry = record.getPreviousEntry(rel_path)
        if job.new_only and previous_entry:
            return

        record_entry = ProcessorPipelineRecordEntry(job.base_dir, rel_path)
        record.addEntry(record_entry)

        # Figure out if a previously processed file is overriding this one.
        # This can happen if a theme file (processed via a mount point)
        # is overridden in the user's website.
        if record.current.hasOverrideEntry(rel_path):
            record_entry.flags |= FLAG_OVERRIDEN
            logger.info(format_timed(start_time,
                    '%s [not baked, overridden]' % rel_path))
            return

        try:
            builder = ProcessingTreeBuilder(pipeline.processors)
            tree_root = builder.build(rel_path)
        except ProcessingTreeError as ex:
            record_entry.errors.append(str(ex))
            logger.error("Error processing %s: %s" % (rel_path, ex))
            return

        print_node(tree_root, recursive=True)
        leaves = tree_root.getLeaves()
        record_entry.rel_outputs = [l.path for l in leaves]
        record_entry.proc_tree = get_node_name_tree(tree_root)
        if tree_root.getProcessor().is_bypassing_structured_processing:
            record_entry.flags |= FLAG_BYPASSED_STRUCTURED_PROCESSING

        force = (pipeline.force or previous_entry is None or
                 not previous_entry.was_processed_successfully)
        if not force:
            force = re_matchany(rel_path, pipeline.force_patterns)

        if force:
            tree_root.setState(STATE_DIRTY, True)

        try:
            runner = ProcessingTreeRunner(
                    job.base_dir, pipeline.tmp_dir,
                    pipeline.out_dir, self.ctx.pipeline_lock)
            if runner.processSubTree(tree_root):
                record_entry.flags |= FLAG_PROCESSED
                logger.info(format_timed(start_time, "[%d] %s" % (self.wid, rel_path)))
        except ProcessingTreeError as ex:
            record_entry.errors.append(str(ex))
            logger.error("Error processing %s: %s" % (rel_path, ex))


def make_re(patterns):
    re_patterns = []
    for pat in patterns:
        if pat[0] == '/' and pat[-1] == '/' and len(pat) > 2:
            re_patterns.append(pat[1:-1])
        else:
            escaped_pat = (re.escape(pat)
                    .replace(r'\*', r'[^/\\]*')
                    .replace(r'\?', r'[^/\\]'))
            re_patterns.append(escaped_pat)
    return [re.compile(p) for p in re_patterns]


def re_matchany(filename, patterns, dirname=None):
    if dirname and dirname != '.':
        filename = os.path.join(dirname, filename)

    # skip patterns use a forward slash regardless of the platform.
    filename = filename.replace('\\', '/')
    for pattern in patterns:
        if pattern.search(filename):
            return True
    return False

