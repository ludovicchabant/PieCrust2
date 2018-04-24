import time
import os.path
import hashlib
import logging
from piecrust.chefutil import (
    format_timed_scope, format_timed)
from piecrust.environment import ExecutionStats
from piecrust.pipelines.base import (
    PipelineJobCreateContext, PipelineJobResultHandleContext, PipelineManager,
    get_pipeline_name_for_source)
from piecrust.pipelines.records import (
    MultiRecordHistory, MultiRecord,
    load_records)
from piecrust.sources.base import REALM_USER, REALM_THEME, REALM_NAMES


logger = logging.getLogger(__name__)


def get_bake_records_path(app, out_dir, *, suffix=''):
    records_cache = app.cache.getCache('baker')
    records_id = hashlib.md5(out_dir.encode('utf8')).hexdigest()
    records_name = '%s%s.records' % (records_id, suffix)
    return records_cache.getCachePath(records_name)


class Baker(object):
    def __init__(self, appfactory, app, out_dir, *,
                 force=False,
                 allowed_pipelines=None,
                 forbidden_pipelines=None,
                 allowed_sources=None,
                 rotate_bake_records=True,
                 keep_unused_records=False):
        self.appfactory = appfactory
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.allowed_pipelines = allowed_pipelines
        self.forbidden_pipelines = forbidden_pipelines
        self.allowed_sources = allowed_sources
        self.rotate_bake_records = rotate_bake_records
        self.keep_unused_records = keep_unused_records

    def bake(self):
        start_time = time.perf_counter()

        # Setup baker.
        logger.debug("  Bake Output: %s" % self.out_dir)
        logger.debug("  Root URL: %s" % self.app.config.get('site/root'))

        # Get into bake mode.
        self.app.config.set('baker/is_baking', True)
        self.app.config.set('site/asset_url_format', '%page_uri%/%filename%')

        stats = self.app.env.stats
        stats.registerTimer('LoadSourceContents', raise_if_registered=False)
        stats.registerTimer('CacheTemplates', raise_if_registered=False)

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
        current_records = MultiRecord()

        # Figure out if we need to clean the cache because important things
        # have changed.
        is_cache_valid = self._handleCacheValidity(previous_records,
                                                   current_records)
        if not is_cache_valid:
            previous_records = MultiRecord()

        # Create the bake records history which tracks what's up-to-date
        # or not since last time we baked to the given output folder.
        record_histories = MultiRecordHistory(
            previous_records, current_records)

        # Pre-create all caches.
        for cache_name in ['app', 'baker', 'pages', 'renders']:
            self.app.cache.getCache(cache_name)

        # Create the pipelines.
        ppmngr = self._createPipelineManager(record_histories)

        # Done with all the setup, let's start the actual work.
        logger.info(format_timed(start_time, "setup baker"))

        # Load all sources, pre-cache templates.
        load_start_time = time.perf_counter()
        self._populateTemplateCaches()
        logger.info(format_timed(load_start_time, "cache templates"))

        # Create the worker processes.
        pool_userdata = _PoolUserData(self, ppmngr)
        pool = self._createWorkerPool(records_path, pool_userdata)

        # Bake the realms.
        self._bakeRealms(pool, ppmngr, record_histories)

        # Handle deletions, collapse records, etc.
        ppmngr.postJobRun()
        ppmngr.deleteStaleOutputs()
        ppmngr.collapseRecords(self.keep_unused_records)

        # All done with the workers. Close the pool and get reports.
        pool_stats = pool.close()
        current_records.stats = _merge_execution_stats(stats, *pool_stats)

        # Shutdown the pipelines.
        ppmngr.shutdownPipelines()

        # Backup previous records, save the current ones.
        current_records.bake_time = time.time()
        current_records.out_dir = self.out_dir
        _save_bake_records(current_records, records_path,
                           rotate_previous=self.rotate_bake_records)

        # All done.
        self.app.config.set('baker/is_baking', False)
        logger.debug(format_timed(start_time, 'done baking'))

        return current_records

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
            # We have no valid previous bake records.
            reason = "need bake records regeneration"
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
            logger.debug(format_timed(
                start_time, "cleaned cache (reason: %s)" % reason,
                colored=False))
            return False
        else:
            current_records.incremental_count += 1
            logger.debug(format_timed(
                start_time, "cache is assumed valid", colored=False))
            return True

    def _createPipelineManager(self, record_histories):
        # Gather all sources by realm -- we're going to bake each realm
        # separately so we can handle "overriding" (i.e. one realm overrides
        # another realm's pages, like the user realm overriding the theme
        # realm).
        #
        # Also, create and initialize each pipeline for each source.
        has_any_pp = False
        ppmngr = PipelineManager(
            self.app, self.out_dir,
            record_histories=record_histories)
        ok_pp = self.allowed_pipelines
        nok_pp = self.forbidden_pipelines
        ok_src = self.allowed_sources
        for source in self.app.sources:
            if ok_src is not None and source.name not in ok_src:
                continue

            pname = get_pipeline_name_for_source(source)
            if ok_pp is not None and pname not in ok_pp:
                continue
            if nok_pp is not None and pname in nok_pp:
                continue

            ppinfo = ppmngr.createPipeline(source)
            logger.debug(
                "Created pipeline '%s' for source: %s" %
                (ppinfo.pipeline.PIPELINE_NAME, source.name))
            has_any_pp = True
        if not has_any_pp:
            raise Exception("The website has no content sources, or the bake "
                            "command was invoked with all pipelines filtered "
                            "out. There's nothing to do.")
        return ppmngr

    def _populateTemplateCaches(self):
        engine_name = self.app.config.get('site/default_template_engine')
        for engine in self.app.plugin_loader.getTemplateEngines():
            if engine_name in engine.ENGINE_NAMES:
                engine.populateCache()
                break

    def _bakeRealms(self, pool, ppmngr, record_histories):
        # Bake the realms -- user first, theme second, so that a user item
        # can override a theme item.
        # Do this for as many times as we have pipeline passes left to do.
        realm_list = [REALM_USER, REALM_THEME]
        pp_by_pass_and_realm = _get_pipeline_infos_by_pass_and_realm(
            ppmngr.getPipelineInfos())

        for pp_pass_num in sorted(pp_by_pass_and_realm.keys()):
            logger.debug("Pipelines pass %d" % pp_pass_num)
            pp_by_realm = pp_by_pass_and_realm[pp_pass_num]
            for realm in realm_list:
                pplist = pp_by_realm.get(realm)
                if pplist is not None:
                    self._bakeRealm(pool, ppmngr, record_histories,
                                    pp_pass_num, realm, pplist)

    def _bakeRealm(self, pool, ppmngr, record_histories,
                   pp_pass_num, realm, pplist):
        start_time = time.perf_counter()

        job_count = 0
        job_descs = {}
        realm_name = REALM_NAMES[realm].lower()
        pool.userdata.cur_pass = pp_pass_num

        for ppinfo in pplist:
            src = ppinfo.source
            pp = ppinfo.pipeline
            jcctx = PipelineJobCreateContext(pp_pass_num, pp.record_name,
                                             record_histories)

            jobs, job_desc = pp.createJobs(jcctx)
            if jobs is not None:
                new_job_count = len(jobs)
                job_count += new_job_count
                pool.queueJobs(jobs)
                if job_desc:
                    job_descs.setdefault(job_desc, []).append(src.name)
            else:
                new_job_count = 0

            logger.debug(
                "Queued %d jobs for source '%s' using pipeline '%s' "
                "(%s)." %
                (new_job_count, src.name, pp.PIPELINE_NAME, realm_name))

        if job_count == 0:
            logger.debug("No jobs queued! Bailing out of this bake pass.")
            return

        pool.wait()

        logger.info(format_timed(
            start_time, "%d jobs completed (%s)." %
            (job_count, ', '.join(
                ['%s %s' % (d, ', '.join(sn))
                 for d, sn in job_descs.items()]))))

    def _logErrors(self, item_spec, errors):
        logger.error("Errors found in %s:" % item_spec)
        for e in errors:
            logger.error("  " + e)

    def _logWorkerException(self, item_spec, exc_data):
        logger.error("Errors found in %s:" % item_spec)
        logger.error(exc_data['value'])
        if self.app.debug:
            logger.error(exc_data['traceback'])

    def _createWorkerPool(self, previous_records_path, pool_userdata):
        from piecrust.workerpool import WorkerPool
        from piecrust.baking.worker import BakeWorkerContext, BakeWorker

        worker_count = self.app.config.get('baker/workers')
        batch_size = self.app.config.get('baker/batch_size')

        ctx = BakeWorkerContext(
            self.appfactory,
            self.out_dir,
            force=self.force,
            previous_records_path=previous_records_path,
            allowed_pipelines=self.allowed_pipelines,
            forbidden_pipelines=self.forbidden_pipelines)
        pool = WorkerPool(
            worker_count=worker_count,
            batch_size=batch_size,
            worker_class=BakeWorker,
            initargs=(ctx,),
            callback=self._handleWorkerResult,
            error_callback=self._handleWorkerError,
            userdata=pool_userdata)
        return pool

    def _handleWorkerResult(self, job, res, userdata):
        cur_pass = userdata.cur_pass
        source_name, item_spec = job['job_spec']

        # Make the pipeline do custom handling to update the record entry.
        ppinfo = userdata.ppmngr.getPipelineInfo(source_name)
        pipeline = ppinfo.pipeline
        record = ppinfo.current_record
        ppmrctx = PipelineJobResultHandleContext(record, job, cur_pass)
        pipeline.handleJobResult(res, ppmrctx)

        # Set the overall success flags if there was an error.
        record_entry = ppmrctx.record_entry
        if not record_entry.success:
            record.success = False
            userdata.records.success = False
            self._logErrors(job['item_spec'], record_entry.errors)

    def _handleWorkerError(self, job, exc_data, userdata):
        # Set the overall success flag.
        source_name, item_spec = job['job_spec']
        ppinfo = userdata.ppmngr.getPipelineInfo(source_name)
        pipeline = ppinfo.pipeline
        record = ppinfo.current_record
        record.success = False
        userdata.records.success = False

        # Add those errors to the record, if possible.
        record_entry_spec = job.get('record_entry_spec', item_spec)
        e = record.getEntry(record_entry_spec)
        if not e:
            e = pipeline.createRecordEntry(item_spec)
            record.addEntry(e)
        e.errors.append(exc_data['value'])
        self._logWorkerException(item_spec, exc_data)

        # Log debug stuff.
        if self.app.debug:
            logger.error(exc_data['traceback'])


class _PoolUserData:
    def __init__(self, baker, ppmngr):
        self.baker = baker
        self.ppmngr = ppmngr
        self.records = ppmngr.record_histories.current
        self.cur_pass = 0


def _get_pipeline_infos_by_pass_and_realm(pp_infos):
    pp_by_pass_and_realm = {}
    for pp_info in pp_infos:
        pp_pass_num = pp_info.pipeline.PASS_NUM
        if isinstance(pp_pass_num, list):
            for ppn in pp_pass_num:
                _add_pipeline_info_to_pass_and_realm_dict(
                    ppn, pp_info, pp_by_pass_and_realm)
        else:
            _add_pipeline_info_to_pass_and_realm_dict(
                pp_pass_num, pp_info, pp_by_pass_and_realm)
    return pp_by_pass_and_realm


def _add_pipeline_info_to_pass_and_realm_dict(pp_pass_num, pp_info,
                                              pp_by_pass_and_realm):
    pp_by_realm = pp_by_pass_and_realm.setdefault(pp_pass_num, {})
    pplist = pp_by_realm.setdefault(
        pp_info.pipeline.source.config['realm'], [])
    pplist.append(pp_info)


def _merge_execution_stats(base_stats, *other_stats):
    total_stats = ExecutionStats()
    total_stats.mergeStats(base_stats)
    for ps in other_stats:
        if ps is not None:
            total_stats.mergeStats(ps)
    return total_stats


def _save_bake_records(records, records_path, *, rotate_previous):
    if rotate_previous:
        records_dir, records_fn = os.path.split(records_path)
        records_id, _ = os.path.splitext(records_fn)
        for i in range(8, -1, -1):
            suffix = '' if i == 0 else '.%d' % i
            records_path_i = os.path.join(
                records_dir,
                '%s%s.records' % (records_id, suffix))
            if os.path.exists(records_path_i):
                records_path_next = os.path.join(
                    records_dir,
                    '%s.%s.records' % (records_id, i + 1))
                if os.path.exists(records_path_next):
                    os.remove(records_path_next)
                os.rename(records_path_i, records_path_next)

    with format_timed_scope(logger, "saved bake records.",
                            level=logging.DEBUG, colored=False):
        records.save(records_path)
