import os
import sys
import logging
import itertools
import threading
import multiprocessing
from piecrust.fastpickle import pickle, unpickle


logger = logging.getLogger(__name__)


class IWorker(object):
    def initialize(self):
        raise NotImplementedError()

    def process(self, job):
        raise NotImplementedError()

    def getReport(self):
        return None


TASK_JOB = 0
TASK_BATCH = 1
TASK_END = 2


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
    if hasattr(params.inqueue, '_writer'):
        params.inqueue._writer.close()
        params.outqueue._reader.close()

    wid = params.wid
    logger.debug("Worker %d initializing..." % wid)

    w = params.worker_class(*params.initargs)
    w.wid = wid
    try:
        w.initialize()
    except Exception as ex:
        logger.error("Working failed to initialize:")
        logger.exception(ex)
        params.outqueue.put(None)
        return

    get = params.inqueue.get
    put = params.outqueue.put

    completed = 0
    while True:
        try:
            task = get()
        except (EOFError, OSError):
            logger.debug("Worker %d encountered connection problem." % wid)
            break

        task_type, task_data = task
        if task_type == TASK_END:
            logger.debug("Worker %d got end task, exiting." % wid)
            try:
                rep = (task_type, True, wid, (wid, w.getReport()))
            except Exception as e:
                if params.wrap_exception:
                    e = multiprocessing.ExceptionWithTraceback(
                            e, e.__traceback__)
                rep = (task_type, False, wid, (wid, e))
            put(rep)
            break

        if task_type == TASK_JOB:
            task_data = (task_data,)

        for t in task_data:
            td = unpickle(t)
            try:
                res = (TASK_JOB, True, wid, w.process(td))
            except Exception as e:
                if params.wrap_exception:
                    e = multiprocessing.ExceptionWithTraceback(
                            e, e.__traceback__)
                res = (TASK_JOB, False, wid, e)
            put(res)

            completed += 1

    logger.debug("Worker %d completed %d tasks." % (wid, completed))


class _WorkerParams(object):
    def __init__(self, wid, inqueue, outqueue, worker_class, initargs=(),
                 wrap_exception=False, is_profiling=False):
        self.wid = wid
        self.inqueue = inqueue
        self.outqueue = outqueue
        self.worker_class = worker_class
        self.initargs = initargs
        self.wrap_exception = wrap_exception
        self.is_profiling = is_profiling


class WorkerPool(object):
    def __init__(self, worker_class, worker_count=None, initargs=(),
                 wrap_exception=False):
        worker_count = worker_count or os.cpu_count() or 1

        self._task_queue = multiprocessing.SimpleQueue()
        self._result_queue = multiprocessing.SimpleQueue()
        self._quick_put = self._task_queue._writer.send
        self._quick_get = self._result_queue._reader.recv

        self._callback = None
        self._error_callback = None
        self._listener = None

        main_module = sys.modules['__main__']
        is_profiling = os.path.basename(main_module.__file__) in [
                'profile.py', 'cProfile.py']

        self._pool = []
        for i in range(worker_count):
            worker_params = _WorkerParams(
                    i, self._task_queue, self._result_queue,
                    worker_class, initargs,
                    wrap_exception=wrap_exception,
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

    def setHandler(self, callback=None, error_callback=None):
        self._callback = callback
        self._error_callback = error_callback

    def queueJobs(self, jobs, handler=None, chunk_size=None):
        if self._closed:
            raise Exception("This worker pool has been closed.")
        if self._listener is not None:
            raise Exception("A previous job queue has not finished yet.")

        if any([not p.is_alive() for p in self._pool]):
            raise Exception("Some workers have prematurely exited.")

        if handler is not None:
            self.setHandler(handler)

        if not hasattr(jobs, '__len__'):
            jobs = list(jobs)
        job_count = len(jobs)

        res = AsyncResult(self, job_count)
        if res._count == 0:
            res._event.set()
            return res

        self._listener = res

        if chunk_size is None:
            chunk_size = max(1, job_count // 50)
            logger.debug("Using chunk size of %d" % chunk_size)

        if chunk_size is None or chunk_size == 1:
            for job in jobs:
                job_data = pickle(job)
                self._quick_put((TASK_JOB, job_data))
        else:
            it = iter(jobs)
            while True:
                batch = tuple([pickle(i)
                               for i in itertools.islice(it, chunk_size)])
                if not batch:
                    break
                self._quick_put((TASK_BATCH, batch))

        return res

    def close(self):
        if self._listener is not None:
            raise Exception("A previous job queue has not finished yet.")

        logger.debug("Closing worker pool...")
        handler = _ReportHandler(len(self._pool))
        self._callback = handler._handle
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

    @staticmethod
    def _handleResults(pool):
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

            task_type, success, wid, data = res
            try:
                if success and pool._callback:
                    pool._callback(data)
                elif not success:
                    if pool._error_callback:
                        pool._error_callback(data)
                    else:
                        logger.error(data)
            except Exception as ex:
                logger.exception(ex)

            if task_type == TASK_JOB:
                pool._listener._onTaskDone()


class AsyncResult(object):
    def __init__(self, pool, count):
        self._pool = pool
        self._count = count
        self._event = threading.Event()

    def ready(self):
        return self._event.is_set()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def _onTaskDone(self):
        self._count -= 1
        if self._count == 0:
            self._pool.setHandler(None)
            self._pool._listener = None
            self._event.set()


class _ReportHandler(object):
    def __init__(self, worker_count):
        self.reports = [None] * worker_count
        self._count = worker_count
        self._received = 0
        self._event = threading.Event()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def _handle(self, res):
        wid, data = res
        if wid < 0 or wid > self._count:
            logger.error("Ignoring report from unknown worker %d." % wid)
            return

        self._received += 1
        self.reports[wid] = data

        if self._received == self._count:
            self._event.set()

    def _handleError(self, res):
        wid, data = res
        logger.error("Worker %d failed to send its report." % wid)
        logger.exception(data)

