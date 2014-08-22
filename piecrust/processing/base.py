import re
import time
import shutil
import os.path
import logging
import threading
from queue import Queue, Empty
from piecrust.chefutil import format_timed
from piecrust.processing.tree import (ProcessingTreeBuilder,
        ProcessingTreeRunner, STATE_DIRTY, print_node)
from piecrust.records import Record


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

    def supportsExtension(self, ext):
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

    def supportsExtension(self, ext):
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

    def supportsExtension(self, ext):
        return ext.lstrip('.') in self.extensions

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


class ProcessorPipelineRecord(Record):
    VERSION = 1

    def __init__(self):
        super(ProcessorPipelineRecord, self).__init__()

    def addEntry(self, item):
        self.entries.append(item)

    def hasOverrideEntry(self, rel_path):
        return self.findEntry(rel_path) is not None

    def findEntry(self, rel_path):
        rel_path = rel_path.lower()
        for entry in self.entries:
            for out_path in entry.rel_outputs:
                if out_path.lower() == rel_path:
                    return entry
        return None


class ProcessorPipelineRecordEntry(object):
    def __init__(self, base_dir, rel_input, is_processed=False,
            is_overridden=False):
        self.base_dir = base_dir
        self.rel_input = rel_input
        self.rel_outputs = []
        self.is_processed = is_processed
        self.is_overridden = is_overridden

    @property
    def path(self):
        return os.path.join(self.base_dir, self.rel_input)


class ProcessingContext(object):
    def __init__(self, base_dir, job_queue, record=None):
        self.base_dir = base_dir
        self.job_queue = job_queue
        self.record = record


class ProcessorPipeline(object):
    def __init__(self, app, mounts, out_dir, force=False,
            skip_patterns=None, force_patterns=None, num_workers=4):
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

    def run(self, src_dir_or_file=None):
        record = ProcessorPipelineRecord()

        # Create the workers.
        pool = []
        queue = Queue()
        abort = threading.Event()
        pipeline_lock = threading.Lock()
        for i in range(self.num_workers):
            ctx = ProcessingWorkerContext(self, record, queue, abort,
                    pipeline_lock)
            worker = ProcessingWorker(i, ctx)
            worker.start()
            pool.append(worker)

        # Invoke pre-processors.
        for proc in self.processors:
            proc.onPipelineStart(self)

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
                self.processDirectory(ctx, src_dir_or_file)
            elif os.path.isfile(src_dir_or_file):
                self.processFile(ctx, src_dir_or_file)

        else:
            # Process everything.
            for path in self.mounts:
                ctx = ProcessingContext(path, queue, record)
                logger.debug("Initiating processing pipeline on: %s" % path)
                self.processDirectory(ctx, path)

        # Wait on all workers.
        for w in pool:
            w.join()
        if abort.is_set():
            raise Exception("Worker pool was aborted.")

        # Invoke post-processors.
        for proc in self.processors:
            proc.onPipelineEnd(self)

        return record

    def processDirectory(self, ctx, start_dir):
        for dirpath, dirnames, filenames in os.walk(start_dir):
            rel_dirpath = os.path.relpath(dirpath, start_dir)
            dirnames[:] = [d for d in dirnames
                    if not re_matchany(d, self.skip_patterns, rel_dirpath)]

            for filename in filenames:
                if re_matchany(filename, self.skip_patterns, rel_dirpath):
                    continue
                self.processFile(ctx, os.path.join(dirpath, filename))

    def processFile(self, ctx, path):
        logger.debug("Queuing: %s" % path)
        job = ProcessingWorkerJob(ctx.base_dir, path)
        ctx.job_queue.put_nowait(job)


class ProcessingWorkerContext(object):
    def __init__(self, pipeline, record, work_queue, abort_event,
            pipeline_lock):
        self.pipeline = pipeline
        self.record = record
        self.work_queue = work_queue
        self.abort_event = abort_event
        self.pipeline_lock = pipeline_lock


class ProcessingWorkerJob(object):
    def __init__(self, base_dir, path):
        self.base_dir = base_dir
        self.path = path


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

        # Figure out if a previously processed file is overriding this one.
        # This can happen if a theme file (processed via a mount point)
        # is overridden in the user's website.
        if record.hasOverrideEntry(rel_path):
            record.addEntry(ProcessorPipelineRecordEntry(
                    job.base_dir, rel_path,
                    is_processed=False, is_overridden=True))
            logger.info(format_timed(start_time,
                    '%s [not baked, overridden]' % rel_path))
            return

        builder = ProcessingTreeBuilder(pipeline.processors)
        tree_root = builder.build(rel_path)
        print_node(tree_root, recursive=True)
        leaves = tree_root.getLeaves()
        fi = ProcessorPipelineRecordEntry(job.base_dir, rel_path)
        fi.rel_outputs = [l.path for l in leaves]
        record.addEntry(fi)

        force = pipeline.force
        if not force:
            force = re_matchany(rel_path, pipeline.force_patterns)

        if force:
            tree_root.setState(STATE_DIRTY, True)

        runner = ProcessingTreeRunner(job.base_dir, pipeline.tmp_dir,
                pipeline.out_dir, self.ctx.pipeline_lock)
        if runner.processSubTree(tree_root):
            fi.is_processed = True
            logger.info(format_timed(start_time, "[%d] %s" % (self.wid, rel_path)))


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

