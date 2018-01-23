import io
import os
import sys
import time
import logging
import threading
import traceback
import multiprocessing
from piecrust.environment import ExecutionStats


logger = logging.getLogger(__name__)

use_fastqueue = False
use_fastpickle = False
use_msgpack = False
use_marshall = False
use_json = False


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


def _get_worker_exception_data(wid):
    t, v, tb = sys.exc_info()
    return {
        'wid': wid,
        'type': str(t),
        'value': '\n'.join(_get_errors(v)),
        'traceback': ''.join(traceback.format_exception(t, v, tb))
    }


def _get_errors(ex):
    errors = []
    while ex is not None:
        msg = str(ex)
        errors.append(msg)
        ex = ex.__cause__
    return errors


TASK_JOB = 0
TASK_JOB_BATCH = 1
TASK_END = 2
_TASK_ABORT_WORKER = 10
_CRITICAL_WORKER_ERROR = 11


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
    try:
        _real_worker_func_unsafe(params)
    except (KeyboardInterrupt, SystemExit):
        # Return silently
        pass
    except Exception as ex:
        logger.exception(ex)
        msg = ("CRITICAL ERROR IN WORKER %d\n%s" % (params.wid, str(ex)))
        params.outqueue.put((
            _CRITICAL_WORKER_ERROR, None, False, params.wid, msg))


def _pre_parse_pytest_args():
    # If we are unit-testing, we need to translate our test logging
    # arguments into something Chef can understand.
    import argparse
    parser = argparse.ArgumentParser()
    # This is adapted from our `conftest.py`.
    parser.add_argument('--log-debug', action='store_true')
    parser.add_argument('--log-file')
    res, _ = parser.parse_known_args(sys.argv[1:])

    chef_args = []
    if res.log_debug:
        chef_args.append('--debug')
    if res.log_file:
        chef_args += ['--log', res.log_file]

    root_logger = logging.getLogger()
    while len(root_logger.handlers) > 0:
        root_logger.removeHandler(root_logger.handlers[0])

    from piecrust.main import _pre_parse_chef_args
    _pre_parse_chef_args(chef_args)


def _real_worker_func_unsafe(params):
    init_start_time = time.perf_counter()

    wid = params.wid

    stats = ExecutionStats()
    stats.registerTimer('WorkerInit')

    # In a context where `multiprocessing` is using the `spawn` forking model,
    # the new process doesn't inherit anything, so we lost all our logging
    # configuration here. Let's set it up again.
    if (hasattr(multiprocessing, 'get_start_method') and
            multiprocessing.get_start_method() == 'spawn'):
        if not params.is_unit_testing:
            from piecrust.main import _pre_parse_chef_args
            _pre_parse_chef_args(sys.argv[1:])
        else:
            _pre_parse_pytest_args()
    elif params.is_unit_testing:
        _pre_parse_pytest_args()

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
        logger.error("Worker %d failed to initialize." % wid)
        logger.exception(ex)
        raise

    stats.stepTimerSince('WorkerInit', init_start_time)

    # Start pumping!
    completed = 0
    time_in_get = 0
    time_in_put = 0
    is_first_get = True
    get = params.inqueue.get
    put = params.outqueue.put

    while True:
        get_start_time = time.perf_counter()
        task = get()
        if not is_first_get:
            time_in_get += (time.perf_counter() - get_start_time)
        else:
            is_first_get = False

        task_type, task_data = task

        # Job task(s)... just do it.
        if task_type == TASK_JOB or task_type == TASK_JOB_BATCH:

            task_data_list = task_data
            if task_type == TASK_JOB:
                task_data_list = [task_data]

            result_list = []

            for td in task_data_list:
                try:
                    worker_res = w.process(td)
                    result_list.append((td, worker_res, True))
                except Exception as e:
                    logger.debug(
                        "Error processing job, sending exception to main process:")
                    logger.debug(traceback.format_exc())
                    error_res = _get_worker_exception_data(wid)
                    result_list.append((td, error_res, False))

            res = (task_type, wid, result_list)
            put_start_time = time.perf_counter()
            put(res)
            time_in_put += (time.perf_counter() - put_start_time)

            completed += len(task_data_list)

        # End task... gather stats to send back to the main process.
        elif task_type == TASK_END:
            logger.debug("Worker %d got end task, exiting." % wid)
            stats.registerTimer('Worker_%d_TaskGet' % wid, time=time_in_get)
            stats.registerTimer('Worker_all_TaskGet', time=time_in_get)
            stats.registerTimer('Worker_%d_ResultPut' % wid, time=time_in_put)
            stats.registerTimer('Worker_all_ResultPut', time=time_in_put)
            try:
                stats.mergeStats(w.getStats())
                stats_data = stats.toData()
                rep = (task_type, wid, [(task_data, (wid, stats_data), True)])
            except Exception as e:
                logger.debug(
                    "Error getting report, sending exception to main process:")
                logger.debug(traceback.format_exc())
                we = _get_worker_exception_data(wid)
                rep = (task_type, wid, [(task_data, (wid, we), False)])
            put(rep)
            break

        # Emergy abort.
        elif task_type == _TASK_ABORT_WORKER:
            logger.debug("Worker %d got abort signal." % wid)
            break

        else:
            raise Exception("Unknown task type: %s" % task_type)

    try:
        w.shutdown()
    except Exception as e:
        logger.error("Worker %s failed to shutdown.")
        logger.exception(e)
        raise

    logger.debug("Worker %d completed %d tasks." % (wid, completed))


class _WorkerParams:
    def __init__(self, wid, inqueue, outqueue, worker_class, initargs=(),
                 is_profiling=False, is_unit_testing=False):
        self.wid = wid
        self.inqueue = inqueue
        self.outqueue = outqueue
        self.worker_class = worker_class
        self.initargs = initargs
        self.is_profiling = is_profiling
        self.is_unit_testing = is_unit_testing


class WorkerPool:
    def __init__(self, worker_class, initargs=(), *,
                 callback=None, error_callback=None,
                 worker_count=None, batch_size=None,
                 userdata=None):
        init_start_time = time.perf_counter()

        stats = ExecutionStats()
        stats.registerTimer('MasterInit')
        self._stats = stats
        self._time_in_put = 0
        self._time_in_get = 0

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
        self._lock_jobs_left = threading.Lock()
        self._lock_workers = threading.Lock()
        self._event = threading.Event()
        self._error_on_join = None
        self._closed = False

        main_module = sys.modules['__main__']
        is_profiling = os.path.basename(main_module.__file__) in [
            'profile.py', 'cProfile.py']
        is_unit_testing = os.path.basename(main_module.__file__) in [
            'py.test']

        self._pool = []
        for i in range(worker_count):
            worker_params = _WorkerParams(
                i, self._task_queue, self._result_queue,
                worker_class, initargs,
                is_profiling=is_profiling,
                is_unit_testing=is_unit_testing)
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

        stats.stepTimerSince('MasterInit', init_start_time)

    @property
    def pool_size(self):
        return len(self._pool)

    def queueJobs(self, jobs):
        if self._closed:
            if self._error_on_join:
                raise self._error_on_join
            raise Exception("This worker pool has been closed.")

        jobs = list(jobs)
        new_job_count = len(jobs)
        if new_job_count > 0:
            put_start_time = time.perf_counter()

            with self._lock_jobs_left:
                self._jobs_left += new_job_count

            self._event.clear()
            bs = self._batch_size
            if not bs:
                for job in jobs:
                    self._quick_put((TASK_JOB, job))
            else:
                cur_offset = 0
                while cur_offset < new_job_count:
                    next_batch_idx = min(cur_offset + bs, new_job_count)
                    job_batch = jobs[cur_offset:next_batch_idx]
                    self._quick_put((TASK_JOB_BATCH, job_batch))
                    cur_offset = next_batch_idx

            self._time_in_put += (time.perf_counter() - put_start_time)
        else:
            with self._lock_jobs_left:
                done = (self._jobs_left == 0)
            if done:
                self._event.set()

    def wait(self, timeout=None):
        if self._closed:
            raise Exception("This worker pool has been closed.")

        ret = self._event.wait(timeout)
        if self._error_on_join:
            raise self._error_on_join
        return ret

    def close(self):
        if self._closed:
            raise Exception("This worker pool has been closed.")
        if self._jobs_left > 0:
            raise Exception("A previous job queue has not finished yet.")
        if not self._event.is_set():
            raise Exception("A previous job queue hasn't been cleared.")

        close_start_time = time.perf_counter()
        logger.debug("Closing worker pool...")
        live_workers = list(filter(lambda w: w is not None, self._pool))
        handler = _ReportHandler(len(live_workers))
        self._callback = handler._handle
        self._error_callback = handler._handleError
        for w in live_workers:
            self._quick_put((TASK_END, None))
        for w in live_workers:
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

        stats = self._stats
        stats.registerTimer('MasterTaskPut', time=self._time_in_put)
        stats.registerTimer('MasterResultGet', time=self._time_in_get)
        stats.registerTimer('MasterClose',
                            time=(time.perf_counter() - close_start_time))

        return [stats] + handler.reports

    def _onResultHandlerCriticalError(self, wid):
        logger.error("Result handler received a critical error from "
                     "worker %d." % wid)
        with self._lock_workers:
            self._pool[wid] = None
            if all(map(lambda w: w is None, self._pool)):
                logger.error("All workers have died!")
                self._closed = True
                self._error_on_join = Exception("All workers have died!")
                self._event.set()
                return False

        return True

    def _onTaskDone(self, done_count):
        with self._lock_jobs_left:
            left = self._jobs_left - done_count
            self._jobs_left = left

        if left == 0:
            self._event.set()

    @staticmethod
    def _handleResults(pool):
        userdata = pool.userdata
        while True:
            try:
                get_start_time = time.perf_counter()
                res = pool._quick_get()
                pool._time_in_get = (time.perf_counter() - get_start_time)
            except (EOFError, OSError):
                logger.debug("Result handler thread encountered connection "
                             "problem, exiting.")
                return

            if res is None:
                logger.debug("Result handler exiting.")
                return

            task_type, wid, res_data_list = res
            for res_data in res_data_list:
                try:
                    task_data, data, success = res_data
                    if success:
                        if pool._callback:
                            pool._callback(task_data, data, userdata)
                    else:
                        if task_type == _CRITICAL_WORKER_ERROR:
                            logger.error(data)
                            do_continue = pool._onResultHandlerCriticalError(wid)
                            if not do_continue:
                                logger.debug("Aborting result handling thread.")
                                return
                        else:
                            if pool._error_callback:
                                pool._error_callback(task_data, data, userdata)
                            else:
                                logger.error(
                                    "Worker %d failed to process a job:" % wid)
                                logger.error(data)
                except Exception as ex:
                    logger.exception(ex)

            if task_type == TASK_JOB or task_type == TASK_JOB_BATCH:
                pool._onTaskDone(len(res_data_list))


class _ReportHandler:
    def __init__(self, worker_count):
        self.reports = [None] * worker_count
        self._count = worker_count
        self._received = 0
        self._lock = threading.Lock()
        self._event = threading.Event()

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def _handle(self, job, res, _):
        wid, data = res
        if wid < 0 or wid > self._count:
            logger.error("Ignoring report from unknown worker %d." % wid)
            return

        stats = ExecutionStats()
        stats.fromData(data)

        with self._lock:
            self.reports[wid] = stats
            self._received += 1
            if self._received == self._count:
                self._event.set()

    def _handleError(self, job, res, _):
        logger.error("Worker %d failed to send its report." % res[0])
        logger.error(res)


class FastQueue:
    def __init__(self):
        self._reader, self._writer = multiprocessing.Pipe(duplex=False)
        self._rlock = multiprocessing.Lock()
        self._wlock = multiprocessing.Lock()
        self._initBuffers()
        self._initSerializer()

    def _initBuffers(self):
        self._rbuf = io.BytesIO()
        self._rbuf.truncate(256)
        self._wbuf = io.BytesIO()
        self._wbuf.truncate(256)

    def _initSerializer(self):
        pass

    def __getstate__(self):
        return (self._reader, self._writer, self._rlock, self._wlock)

    def __setstate__(self, state):
        (self._reader, self._writer, self._rlock, self._wlock) = state
        self._initBuffers()

    def get(self):
        with self._rlock:
            self._rbuf.seek(0)
            try:
                with self._rbuf.getbuffer() as b:
                    bufsize = self._reader.recv_bytes_into(b)
            except multiprocessing.BufferTooShort as e:
                bufsize = len(e.args[0])
                self._rbuf.truncate(bufsize * 2)
                self._rbuf.seek(0)
                self._rbuf.write(e.args[0])

        self._rbuf.seek(0)
        return _unpickle(self, self._rbuf, bufsize)

    def put(self, obj):
        self._wbuf.seek(0)
        _pickle(self, obj, self._wbuf)
        size = self._wbuf.tell()

        self._wbuf.seek(0)
        with self._wlock:
            with self._wbuf.getbuffer() as b:
                self._writer.send_bytes(b, 0, size)


class _BufferWrapper:
    def __init__(self, buf, read_size=0):
        self._buf = buf
        self._read_size = read_size

    def write(self, data):
        self._buf.write(data.encode('utf8'))

    def read(self):
        return self._buf.read(self._read_size).decode('utf8')


if use_fastpickle:
    from piecrust import fastpickle

    def _pickle_fast(queue, obj, buf):
        fastpickle.pickle_intob(obj, buf)

    def _unpickle_fast(queue, buf, bufsize):
        return fastpickle.unpickle_fromb(buf, bufsize)

    _pickle = _pickle_fast
    _unpickle = _unpickle_fast

elif use_msgpack:
    import msgpack

    def _pickle_msgpack(queue, obj, buf):
        buf.write(queue._packer.pack(obj))

    def _unpickle_msgpack(queue, buf, bufsize):
        queue._unpacker.feed(buf.getbuffer())
        for o in queue._unpacker:
            return o
        # return msgpack.unpack(buf)

    def _init_msgpack(queue):
        queue._packer = msgpack.Packer()
        queue._unpacker = msgpack.Unpacker()

    _pickle = _pickle_msgpack
    _unpickle = _unpickle_msgpack
    FastQueue._initSerializer = _init_msgpack

elif use_marshall:
    import marshal

    def _pickle_marshal(queue, obj, buf):
        marshal.dump(obj, buf)

    def _unpickle_marshal(queue, buf, bufsize):
        return marshal.load(buf)

    _pickle = _pickle_marshal
    _unpickle = _unpickle_marshal

elif use_json:
    import json

    def _pickle_json(queue, obj, buf):
        buf = _BufferWrapper(buf)
        json.dump(obj, buf, indent=None, separators=(',', ':'))

    def _unpickle_json(queue, buf, bufsize):
        buf = _BufferWrapper(buf, bufsize)
        return json.load(buf)

    _pickle = _pickle_json
    _unpickle = _unpickle_json

else:
    import pickle

    def _pickle_default(queue, obj, buf):
        pickle.dump(obj, buf, pickle.HIGHEST_PROTOCOL)

    def _unpickle_default(queue, buf, bufsize):
        return pickle.load(buf)

    _pickle = _pickle_default
    _unpickle = _unpickle_default
