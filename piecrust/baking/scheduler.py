import logging
import threading


logger = logging.getLogger(__name__)


class BakeScheduler(object):
    _EMPTY = object()
    _WAIT = object()

    def __init__(self, record, jobs=None):
        self.record = record
        self.jobs = list(jobs) if jobs is not None else []
        self._active_jobs = []
        self._lock = threading.Lock()
        self._added_event = threading.Event()
        self._done_event = threading.Event()

    def addJob(self, job):
        logger.debug("Queuing job '%s:%s'." % (
                job.factory.source.name, job.factory.rel_path))
        with self._lock:
            self.jobs.append(job)
        self._added_event.set()

    def onJobFinished(self, job):
        logger.debug("Removing job '%s:%s'." % (
                job.factory.source.name, job.factory.rel_path))
        with self._lock:
            self._active_jobs.remove(job)
        self._done_event.set()

    def getNextJob(self, wait_timeout=None, empty_timeout=None):
        self._added_event.clear()
        self._done_event.clear()
        job = self._doGetNextJob()
        while job in (self._EMPTY, self._WAIT):
            if job == self._EMPTY:
                if empty_timeout is None:
                    return None
                logger.debug("Waiting for a new job to be added...")
                res = self._added_event.wait(empty_timeout)
            elif job == self._WAIT:
                if wait_timeout is None:
                    return None
                logger.debug("Waiting for a job to be finished...")
                res = self._done_event.wait(wait_timeout)
            if not res:
                logger.debug("Timed-out. No job found.")
                return None
            job = self._doGetNextJob()
        return job

    def _doGetNextJob(self):
        with self._lock:
            if len(self.jobs) == 0:
                return self._EMPTY

            job = self.jobs.pop(0)
            first_job = job
            while True:
                ready, wait_on_src = self._isJobReady(job)
                if ready:
                    break

                logger.debug("Job '%s:%s' isn't ready yet: waiting on pages "
                             "from source '%s' to finish baking." %
                             (job.factory.source.name,
                                 job.factory.rel_path, wait_on_src))
                self.jobs.append(job)
                job = self.jobs.pop(0)
                if job == first_job:
                    # None of the jobs are ready... we need to wait.
                    self.jobs.append(job)
                    return self._WAIT

            logger.debug(
                    "Job '%s:%s' is ready to go, moving to active queue." %
                    (job.factory.source.name, job.factory.rel_path))
            self._active_jobs.append(job)
            return job

    def _isJobReady(self, job):
        e = self.record.getPreviousEntry(
                job.factory.source.name,
                job.factory.rel_path,
                taxonomy_info=job.record_entry.taxonomy_info)
        if not e:
            return (True, None)
        used_source_names = e.getAllUsedSourceNames()
        for sn in used_source_names:
            if sn == job.factory.source.name:
                continue
            if any(filter(lambda j: j.factory.source.name == sn,
                          self.jobs)):
                return (False, sn)
            if any(filter(lambda j: j.factory.source.name == sn,
                          self._active_jobs)):
                return (False, sn)
        return (True, None)

