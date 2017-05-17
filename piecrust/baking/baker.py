import time
import os.path
import hashlib
import logging
from piecrust.baking.worker import BakeJob
from piecrust.chefutil import (
    format_timed_scope, format_timed)
from piecrust.environment import ExecutionStats
from piecrust.pipelines.base import PipelineContext
from piecrust.pipelines.records import (
    MultiRecordHistory, MultiRecord, RecordEntry,
    load_records)
from piecrust.sources.base import REALM_USER, REALM_THEME


logger = logging.getLogger(__name__)


def get_bake_records_path(app, out_dir):
    records_cache = app.cache.getCache('baker')
    records_id = hashlib.md5(out_dir.encode('utf8')).hexdigest()
    records_name = records_id + '.record'
    return records_cache.getCachePath(records_name)


class Baker(object):
    def __init__(self, appfactory, app, out_dir,
                 force=False, allowed_pipelines=None):
        self.appfactory = appfactory
        self.app = app
        self.out_dir = out_dir
        self.force = force

        self._pipeline_classes = {}
        for pclass in app.plugin_loader.getPipelines():
            self._pipeline_classes[pclass.PIPELINE_NAME] = pclass

        self.allowed_pipelines = allowed_pipelines
        if allowed_pipelines is None:
            self.allowed_pipelines = list(self._pipeline_classes.keys())

        self._records = None

    def bake(self):
        start_time = time.perf_counter()
        logger.debug("  Bake Output: %s" % self.out_dir)
        logger.debug("  Root URL: %s" % self.app.config.get('site/root'))

        # Get into bake mode.
        self.app.config.set('baker/is_baking', True)
        self.app.config.set('site/base_asset_url_format', '%uri')

        # Make sure the output directory exists.
        if not os.path.isdir(self.out_dir):
            os.makedirs(self.out_dir, 0o755)

        # Load/create the bake records.
        records_path = get_bake_records_path(
            self.app, self.out_dir)
        if not self.force and os.path.isfile(records_path):
            with format_timed_scope(logger, "loaded previous bake records",
                                    level=logging.DEBUG, colored=False):
                previous_records = load_records(records_path)
        else:
            previous_records = MultiRecord()
        self._records = MultiRecord()

        # Figure out if we need to clean the cache because important things
        # have changed.
        is_cache_valid = self._handleCacheValidity(previous_records,
                                                   self._records)
        if not is_cache_valid:
            previous_records = MultiRecord()

        # Create the bake records history which tracks what's up-to-date
        # or not since last time we baked to the given output folder.
        record_history = MultiRecordHistory(previous_records, self._records)

        # Pre-create all caches.
        for cache_name in ['app', 'baker', 'pages', 'renders']:
            self.app.cache.getCache(cache_name)

        # Gather all sources by realm -- we're going to bake each realm
        # separately so we can handle "overriding" (i.e. one realm overrides
        # another realm's pages, like the user realm overriding the theme
        # realm).
        #
        # Also, create and initialize each pipeline for each source.
        sources_by_realm = {}
        ppctx = PipelineContext(self.out_dir, record_history,
                                force=self.force)
        for source in self.app.sources:
            pname = source.config['pipeline']
            if pname in self.allowed_pipelines:
                srclist = sources_by_realm.setdefault(
                    source.config['realm'], [])

                pp = self._pipeline_classes[pname](source)
                pp.initialize(ppctx)
                srclist.append((source, pp))
            else:
                logger.debug(
                    "Skip source '%s' because pipeline '%s' is ignored." %
                    (source.name, pname))

        # Create the worker processes.
        pool = self._createWorkerPool(records_path)

        # Bake the realms -- user first, theme second, so that a user item
        # can override a theme item.
        realm_list = [REALM_USER, REALM_THEME]
        for realm in realm_list:
            srclist = sources_by_realm.get(realm)
            if srclist is not None:
                self._bakeRealm(record_history, pool, realm, srclist)

        # All done with the workers. Close the pool and get reports.
        pool_stats = pool.close()
        total_stats = ExecutionStats()
        for ps in pool_stats:
            if ps is not None:
                total_stats.mergeStats(ps)
        record_history.current.stats = total_stats

        # Shutdown the pipelines.
        for realm in realm_list:
            srclist = sources_by_realm.get(realm)
            if srclist is not None:
                for _, pp in srclist:
                    pp.shutdown(ppctx)

        # Backup previous records.
        records_dir, records_fn = os.path.split(records_path)
        records_id, _ = os.path.splitext(records_fn)
        for i in range(8, -1, -1):
            suffix = '' if i == 0 else '.%d' % i
            records_path_i = os.path.join(
                records_dir,
                '%s%s.record' % (records_id, suffix))
            if os.path.exists(records_path_i):
                records_path_next = os.path.join(
                    records_dir,
                    '%s.%s.record' % (records_id, i + 1))
                if os.path.exists(records_path_next):
                    os.remove(records_path_next)
                os.rename(records_path_i, records_path_next)

        # Save the bake record.
        with format_timed_scope(logger, "saved bake records.",
                                level=logging.DEBUG, colored=False):
            record_history.current.bake_time = time.time()
            record_history.current.out_dir = self.out_dir
            record_history.current.save(records_path)

        # All done.
        self.app.config.set('baker/is_baking', False)
        logger.debug(format_timed(start_time, 'done baking'))

        self._records = None
        return record_history.current

    def _handleCacheValidity(self, previous_records, current_records):
        start_time = time.perf_counter()

        reason = None
        if self.force:
            reason = "ordered to"
        elif not self.app.config.get('__cache_valid'):
            # The configuration file was changed, or we're running a new
            # version of the app.
            reason = "not valid anymore"
        elif previous_records.invalidated:
            # We have no valid previous bake record.
            reason = "need bake record regeneration"
        else:
            # Check if any template has changed since the last bake. Since
            # there could be some advanced conditional logic going on, we'd
            # better just force a bake from scratch if that's the case.
            max_time = 0
            for d in self.app.templates_dirs:
                for dpath, _, filenames in os.walk(d):
                    for fn in filenames:
                        full_fn = os.path.join(dpath, fn)
                        max_time = max(max_time, os.path.getmtime(full_fn))
            if max_time >= previous_records.bake_time:
                reason = "templates modified"

        if reason is not None:
            # We have to bake everything from scratch.
            self.app.cache.clearCaches(except_names=['app', 'baker'])
            self.force = True
            current_records.incremental_count = 0
            previous_records = MultiRecord()
            logger.info(format_timed(
                start_time, "cleaned cache (reason: %s)" % reason))
            return False
        else:
            current_records.incremental_count += 1
            logger.debug(format_timed(
                start_time, "cache is assumed valid", colored=False))
            return True

    def _bakeRealm(self, record_history, pool, realm, srclist):
        for source, pp in srclist:
            logger.debug("Queuing jobs for source '%s' using pipeline '%s'." %
                         (source.name, pp.PIPELINE_NAME))
            jobs = [BakeJob(source.name, item.spec, item.metadata)
                    for item in source.getAllContents()]
            pool.queueJobs(jobs)
        pool.wait()

    def _logErrors(self, item_spec, errors):
        logger.error("Errors found in %s:" % item_spec)
        for e in errors:
            logger.error("  " + e)

    def _createWorkerPool(self, previous_records_path):
        from piecrust.workerpool import WorkerPool
        from piecrust.baking.worker import BakeWorkerContext, BakeWorker

        worker_count = self.app.config.get('baker/workers')
        batch_size = self.app.config.get('baker/batch_size')

        ctx = BakeWorkerContext(
            self.appfactory,
            self.out_dir,
            force=self.force,
            previous_records_path=previous_records_path,
            allowed_pipelines=self.allowed_pipelines)
        pool = WorkerPool(
            worker_count=worker_count,
            batch_size=batch_size,
            worker_class=BakeWorker,
            initargs=(ctx,),
            callback=self._handleWorkerResult,
            error_callback=self._handleWorkerError)
        return pool

    def _handleWorkerResult(self, job, res):
        record_name = self._getRecordName(job)
        record = self._records.getRecord(record_name)
        record.entries.append(res.record)
        if not res.record.success:
            record.success = False
            self._records.success = False
            self._logErrors(job.item_spec, res.record.errors)

    def _handleWorkerError(self, job, exc_data):
        e = RecordEntry()
        e.item_spec = job.item_spec
        e.errors.append(str(exc_data))

        record_name = self._getRecordName(job)
        record = self._records.getRecord(record_name)
        record.entries.append(e)

        record.success = False
        self._records.success = False

        self._logErrors(job.item_spec, e.errors)
        if self.app.debug:
            logger.error(exc_data.traceback)

    def _getRecordName(self, job):
        sn = job.source_name
        ppn = self.app.getSource(sn).config['pipeline']
        return '%s@%s' % (sn, ppn)
