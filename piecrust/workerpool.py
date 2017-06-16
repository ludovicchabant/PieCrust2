import io
import os
import sys
import time
import pickle
import logging
import threading
import traceback
import multiprocessing
from piecrust import fastpickle
from piecrust.environment import ExecutionStats


logger = logging.getLogger(__name__)

use_fastqueue = False
use_fastpickle = False


class IWorker(object):
    """ Interface for a pool worker.
    """
    def initialize(self):
        raise NotImplementedError()

    def process(self, job):
        raise NotImplementedError()

    def getStats(self):
        return None

    def shutdown(self):
        pass


class WorkerExceptionData:
    def __init__(self, wid):
        super().__init__()
        self.wid = wid
        t, v, tb = sys.exc_info()
        self.type = t
        self.value = '\n'.join(_get_errors(v))
        self.traceback = ''.join(traceback.format_exception(t, v, tb))

    def __str__(self):
        return str(self.value)


def _get_errors(ex):
    errors = []
    while ex is not None:
        msg = str(ex)
        errors.append(msg)
        ex = ex.__cause__
    return errors


TASK_JOB = 0
TASK_END = 1


def worker_func(params):
    if params.is_profiling:
        try:
            import cProfile as profile
        except ImportError:
            import profile

        params.is_profiling = False
        name = params.worker_class.__name__
        profile.runctx('_real_worker_func(params)',
                       globals(), locals(),
                       filename='%s-%d.prof' % (name, params.wid))
    else:
        _real_worker_func(params)


def _real_worker_func(params):
    wid = params.wid

    stats = ExecutionStats()
    stats.registerTimer('WorkerInit')
    init_start_time = time.perf_counter()

    # In a context where `multiprocessing` is using the `spawn` forking model,
    # the new process doesn't inherit anything, so we lost all our logging
    # configuration here. Let's set it up again.
    if (hasattr(multiprocessing, 'get_start_method') and
            multiprocessing.get_start_method() == 'spawn'):
        from piecrust.main import _pre_parse_chef_args
        _pre_parse_chef_args(sys.argv[1:])

    from piecrust.main import ColoredFormatter
    root_logger = logging.getLogger()
    root_logger.handlers[0].setFormatter(ColoredFormatter(
        ('[W-%d]' % wid) + '[%(name)s] %(message)s'))

    logger.debug("Worker %d initializing..." % wid)

    # We don't need those.
    params.inqueue._writer.close()
    params.outqueue._reader.close()

    # Initialize the underlying worker class.
    w = params.worker_class(*params.initargs)
    w.wid = wid
    try:
        w.initialize()
    except Exception as ex:
        logger.error("Working failed to initialize:")
        logger.exception(ex)
        params.outqueue.put(None)
        return

    stats.stepTimerSince('WorkerInit', init_start_time)

    # Start pumping!
    completed = 0
    time_in_get = 0
    time_in_put = 0
    get = params.inqueue.get
    put = params.outqueue.put

    while True:
        get_start_time = time.perf_counter()
        task = get()
        time_in_get += (time.perf_counter() - get_start_time)

        task_type, task_data = task

        # End task... gather stats to send back to the main process.
        if task_type == TASK_END:
            logger.debug("Worker %d got end task, exiting." % wid)
            stats.registerTimer('WorkerTaskGet', time=time_in_get)
            stats.registerTimer('WorkerResultPut', time=time_in_put)
            try:
                stats.mergeStats(w.getStats())
                rep = (task_type, task_data, True, wid, (wid, stats))
            except Exception as e:
                logger.debug(
                    "Error getting report, sending exception to main process:")
                logger.debug(traceback.format_exc())
                we = WorkerExceptionData(wid)
                rep = (task_type, task_data, False, wid, (wid, we))
            put(rep)
            break

        # Job task... just do it.
        elif task_type == TASK_JOB:
            try:
                res = (task_type, task_data, True, wid, w.process(task_data))
            except Exception as e:
                logger.debug(
                    "Error processing job, sending exception to main process:")
                logger.debug(traceback.format_exc())
                we = WorkerExceptionData(wid)
                res = (task_type, task_data, False, wid, we)

            put_start_time = time.perf_counter()
            put(res)
            time_in_put += (time.perf_counter() - put_start_time)

            completed += 1

        else:
            raise Exception("Unknown task type: %s" % task_type)

    w.shutdown()
    logger.debug("Worker %d completed %d tasks." % (wid, completed))


class _WorkerParams:
    def __init__(self, wid, inqueue, outqueue, worker_class, initargs=(),
                 is_profiling=False):
        self.wid = wid
        self.inqueue = inqueue
        self.outqueue = outqueue
        self.worker_class = worker_class
        self.initargs = initargs
        self.is_profiling = is_profiling


class WorkerPool:
    def __init__(self, worker_class, initargs=(), *,
                 callback=None, error_callback=None,
                 worker_count=None, batch_size=None,
                 userdata=None):
        self.userdata = userdata

        worker_count = worker_count or os.cpu_count() or 1

        if use_fastqueue:
            self._task_queue = FastQueue()
            self._result_queue = FastQueue()
            self._quick_put = self._task_queue.put
            self._quick_get = self._result_queue.get
        else:
            self._task_queue = multiprocessing.SimpleQueue()
            self._result_queue = multiprocessing.SimpleQueue()
            self._quick_put = self._task_queue.put
            self._quick_get = self._result_queue.get

        self._callback = callback
        self._error_callback = error_callback
        self._batch_size = batch_size
        self._jobs_left = 0
        self._event = threading.Event()

        main_module = sys.modules['__main__']
        is_profiling = os.path.basename(main_module.__file__) in [
            'profile.py', 'cProfile.py']

        self._pool = []
        for i in range(worker_count):
            worker_params = _WorkerParams(
                i, self._task_queue, self._result_queue,
                worker_class, initargs,
                is_profiling=is_profiling)
            w = multiprocessing.Process(target=worker_func,
                                        args=(worker_params,))
            w.name = w.name.replace('Process', 'PoolWorker')
            w.daemon = True
            w.start()
            self._pool.append(w)

        self._result_handler = threading.Thread(
            target=WorkerPool._handleResults,
            args=(self,))
        self._result_handler.daemon = True
        self._result_handler.start()

        self._closed = False

    def queueJobs(self, jobs):
        if self._closed:
            raise Exception("This worker pool has been closed.")

        for job in jobs:
            self._jobs_left += 1
            self._quick_put((TASK_JOB, job))

        if self._jobs_left > 0:
            self._event.clear()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def close(self):
        if self._jobs_left > 0 or not self._event.is_set():
            raise Exception("A previous job queue has not finished yet.")

        logger.debug("Closing worker pool...")
        handler = _ReportHandler(len(self._pool))
        self._callback = handler._handle
        self._error_callback = handler._handleError
        for w in self._pool:
            self._quick_put((TASK_END, None))
        for w in self._pool:
            w.join()

        logger.debug("Waiting for reports...")
        if not handler.wait(2):
            missing = handler.reports.index(None)
            logger.warning(
                "Didn't receive all worker reports before timeout. "
                "Missing report from worker %d." % missing)

        logger.debug("Exiting result handler thread...")
        self._result_queue.put(None)
        self._result_handler.join()
        self._closed = True

        return handler.reports

    def _onTaskDone(self):
        self._jobs_left -= 1
        if self._jobs_left == 0:
            self._event.set()

    @staticmethod
    def _handleResults(pool):
        userdata = pool.userdata
        while True:
            try:
                res = pool._quick_get()
            except (EOFError, OSError):
                logger.debug("Result handler thread encountered connection "
                             "problem, exiting.")
                return

            if res is None:
                logger.debug("Result handler exiting.")
                break

            task_type, task_data, success, wid, data = res
            try:
                if success:
                    if pool._callback:
                        pool._callback(task_data, data, userdata)
                else:
                    if pool._error_callback:
                        pool._error_callback(task_data, data, userdata)
                    else:
                        logger.error(
                            "Worker %d failed to process a job:" % wid)
                        logger.error(data)
            except Exception as ex:
                logger.exception(ex)

            if task_type == TASK_JOB:
                pool._onTaskDone()


class _ReportHandler:
    def __init__(self, worker_count):
        self.reports = [None] * worker_count
        self._count = worker_count
        self._received = 0
        self._event = threading.Event()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def _handle(self, job, res, _):
        wid, data = res
        if wid < 0 or wid > self._count:
            logger.error("Ignoring report from unknown worker %d." % wid)
            return

        self._received += 1
        self.reports[wid] = data

        if self._received == self._count:
            self._event.set()

    def _handleError(self, job, res, _):
        logger.error("Worker %d failed to send its report." % res.wid)
        logger.error(res)


class FastQueue:
    def __init__(self):
        self._reader, self._writer = multiprocessing.Pipe(duplex=False)
        self._rlock = multiprocessing.Lock()
        self._wlock = multiprocessing.Lock()
        self._initBuffers()

    def _initBuffers(self):
        self._rbuf = io.BytesIO()
        self._rbuf.truncate(256)
        self._wbuf = io.BytesIO()
        self._wbuf.truncate(256)

    def __getstate__(self):
        return (self._reader, self._writer, self._rlock, self._wlock)

    def __setstate__(self, state):
        (self._reader, self._writer, self._rlock, self._wlock) = state
        self._initBuffers()

    def get(self):
        with self._rlock:
            try:
                with self._rbuf.getbuffer() as b:
                    bufsize = self._reader.recv_bytes_into(b)
            except multiprocessing.BufferTooShort as e:
                bufsize = len(e.args[0])
                self._rbuf.truncate(bufsize * 2)
                self._rbuf.seek(0)
                self._rbuf.write(e.args[0])

        self._rbuf.seek(0)
        return _unpickle(self._rbuf, bufsize)

    def put(self, obj):
        self._wbuf.seek(0)
        _pickle(obj, self._wbuf)
        size = self._wbuf.tell()

        self._wbuf.seek(0)
        with self._wlock:
            with self._wbuf.getbuffer() as b:
                self._writer.send_bytes(b, 0, size)


def _pickle_fast(obj, buf):
    fastpickle.pickle_intob(obj, buf)


def _unpickle_fast(buf, bufsize):
    return fastpickle.unpickle_fromb(buf, bufsize)


def _pickle_default(obj, buf):
    pickle.dump(obj, buf)


def _unpickle_default(buf, bufsize):
    return pickle.load(buf)


if use_fastpickle:
    _pickle = _pickle_fast
    _unpickle = _unpickle_fast
else:
    _pickle = _pickle_default
    _unpickle = _unpickle_default

