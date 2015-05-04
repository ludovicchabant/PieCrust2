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
        FLAG_PREPARED, FLAG_PROCESSED, FLAG_OVERRIDEN,
        FLAG_BYPASSED_STRUCTURED_PROCESSING)
from piecrust.processing.tree import (
        ProcessingTreeBuilder, ProcessingTreeRunner,
        ProcessingTreeError, ProcessorError,
        STATE_DIRTY,
        print_node, get_node_name_tree)


logger = logging.getLogger(__name__)


re_ansicolors = re.compile('\033\\[\d+m')


PRIORITY_FIRST = -1
PRIORITY_NORMAL = 0
PRIORITY_LAST = 1


split_processor_names_re = re.compile(r'[ ,]+')


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


class ExternalProcessException(Exception):
    def __init__(self, stderr_data):
        self.stderr_data = stderr_data

    def __str__(self):
        return self.stderr_data


class ProcessingContext(object):
    def __init__(self, base_dir, mount_info, job_queue, record=None):
        self.base_dir = base_dir
        self.mount_info = mount_info
        self.job_queue = job_queue
        self.record = record


class ProcessorPipeline(object):
    def __init__(self, app, out_dir, force=False):
        assert app and out_dir
        self.app = app
        self.out_dir = out_dir
        self.force = force

        tmp_dir = app.sub_cache_dir
        if not tmp_dir:
            import tempfile
            tmp_dir = os.path.join(tempfile.gettempdir(), 'piecrust')
        self.tmp_dir = os.path.join(tmp_dir, 'proc')

        baker_params = app.config.get('baker') or {}

        assets_dirs = baker_params.get('assets_dirs', app.assets_dirs)
        self.mounts = make_mount_infos(assets_dirs, self.app.root_dir)

        self.num_workers = baker_params.get('workers', 4)

        ignores = baker_params.get('ignore', [])
        ignores += [
                '_cache', '_counter',
                'theme_info.yml',
                '.DS_Store', 'Thumbs.db',
                '.git*', '.hg*', '.svn']
        self.skip_patterns = make_re(ignores)
        self.force_patterns = make_re(baker_params.get('force', []))

        self.processors = app.plugin_loader.getProcessors()

    def addSkipPatterns(self, patterns):
        self.skip_patterns += make_re(patterns)

    def filterProcessors(self, authorized_names):
        self.processors = self.getFilteredProcessors(authorized_names)

    def getFilteredProcessors(self, authorized_names):
        if not authorized_names or authorized_names == 'all':
            return self.processors

        if isinstance(authorized_names, str):
            authorized_names = split_processor_names_re.split(authorized_names)

        procs = []
        has_star = 'all' in authorized_names
        for p in self.processors:
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

    def run(self, src_dir_or_file=None, *,
            delete=True, previous_record=None, save_record=True):
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
            for name, info in self.mounts.items():
                path = info['path']
                if src_dir_or_file[:len(path)] == path:
                    base_dir = path
                    mount_info = info
                    break
            else:
                known_roots = [i['path'] for i in self.mounts.values()]
                raise Exception("Input path '%s' is not part of any known "
                                "mount point: %s" %
                                (src_dir_or_file, known_roots))

            ctx = ProcessingContext(base_dir, mount_info, queue, record)
            logger.debug("Initiating processing pipeline on: %s" % src_dir_or_file)
            if os.path.isdir(src_dir_or_file):
                self.processDirectory(ctx, src_dir_or_file)
            elif os.path.isfile(src_dir_or_file):
                self.processFile(ctx, src_dir_or_file)

        else:
            # Process everything.
            for name, info in self.mounts.items():
                path = info['path']
                ctx = ProcessingContext(path, info, queue, record)
                logger.debug("Initiating processing pipeline on: %s" % path)
                self.processDirectory(ctx, path)

        # Wait on all workers.
        record.current.success = True
        for w in pool:
            w.join()
            record.current.success &= w.success
        if abort.is_set():
            raise Exception("Worker pool was aborted.")

        # Handle deletions.
        if delete:
            for path, reason in record.getDeletions():
                logger.debug("Removing '%s': %s" % (path, reason))
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
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
        job = ProcessingWorkerJob(ctx.base_dir, ctx.mount_info, path)
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
    def __init__(self, base_dir, mount_info, path):
        self.base_dir = base_dir
        self.mount_info = mount_info
        self.path = path


class ProcessingWorker(threading.Thread):
    def __init__(self, wid, ctx):
        super(ProcessingWorker, self).__init__()
        self.wid = wid
        self.ctx = ctx
        self.success = True

    def run(self):
        while(not self.ctx.abort_event.is_set()):
            try:
                job = self.ctx.work_queue.get(True, 0.1)
            except Empty:
                logger.debug("[%d] No more work... shutting down." % self.wid)
                break

            try:
                success = self._unsafeRun(job)
                logger.debug("[%d] Done with file." % self.wid)
                self.ctx.work_queue.task_done()
                self.success &= success
            except Exception as ex:
                self.ctx.abort_event.set()
                self.success = False
                logger.error("[%d] Critical error, aborting." % self.wid)
                logger.exception(ex)
                break

    def _unsafeRun(self, job):
        start_time = time.clock()
        pipeline = self.ctx.pipeline
        record = self.ctx.record

        rel_path = os.path.relpath(job.path, job.base_dir)
        previous_entry = record.getPreviousEntry(rel_path)

        record_entry = ProcessorPipelineRecordEntry(job.base_dir, rel_path)
        record.addEntry(record_entry)

        # Figure out if a previously processed file is overriding this one.
        # This can happen if a theme file (processed via a mount point)
        # is overridden in the user's website.
        if record.current.hasOverrideEntry(rel_path):
            record_entry.flags |= FLAG_OVERRIDEN
            logger.info(format_timed(start_time,
                    '%s [not baked, overridden]' % rel_path))
            return True

        processors = pipeline.getFilteredProcessors(
                job.mount_info['processors'])
        try:
            builder = ProcessingTreeBuilder(processors)
            tree_root = builder.build(rel_path)
            record_entry.flags |= FLAG_PREPARED
        except ProcessingTreeError as ex:
            msg = str(ex)
            logger.error("Error preparing %s:\n%s" % (rel_path, msg))
            while ex:
                record_entry.errors.append(str(ex))
                ex = ex.__cause__
            return False

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
                logger.info(format_timed(
                    start_time, "[%d] %s" % (self.wid, rel_path)))
            return True
        except ProcessingTreeError as ex:
            msg = str(ex)
            if isinstance(ex, ProcessorError):
                msg = str(ex.__cause__)
            logger.error("Error processing %s:\n%s" % (rel_path, msg))
            while ex:
                msg = re_ansicolors.sub('', str(ex))
                record_entry.errors.append(msg)
                ex = ex.__cause__
            return False


def make_mount_infos(mounts, root_dir):
    if isinstance(mounts, list):
        mounts = {m: {} for m in mounts}

    for name, info in mounts.items():
        if not isinstance(info, dict):
            raise Exception("Asset directory info for '%s' is not a "
                            "dictionary." % name)
        info.setdefault('processors', 'all -uglifyjs -cleancss')
        info['path'] = os.path.join(root_dir, name)

    return mounts


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

