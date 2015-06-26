import copy
import time
import os.path
import queue
import hashlib
import logging
import multiprocessing
from piecrust.baking.records import (
        BakeRecordEntry, TransitionalBakeRecord, TaxonomyInfo)
from piecrust.baking.worker import (
        BakeWorkerJob, LoadJobPayload, RenderFirstSubJobPayload,
        BakeJobPayload,
        JOB_LOAD, JOB_RENDER_FIRST, JOB_BAKE)
from piecrust.chefutil import (
        format_timed_scope, format_timed)
from piecrust.sources.base import (
        REALM_NAMES, REALM_USER, REALM_THEME)


logger = logging.getLogger(__name__)


class Baker(object):
    def __init__(self, app, out_dir, force=False):
        assert app and out_dir
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.num_workers = app.config.get('baker/workers',
                                          multiprocessing.cpu_count())

        # Remember what taxonomy pages we should skip
        # (we'll bake them repeatedly later with each taxonomy term)
        self.taxonomy_pages = []
        logger.debug("Gathering taxonomy page paths:")
        for tax in self.app.taxonomies:
            for src in self.app.sources:
                tax_page_ref = tax.getPageRef(src)
                for path in tax_page_ref.possible_paths:
                    self.taxonomy_pages.append(path)
                    logger.debug(" - %s" % path)

        # Register some timers.
        self.app.env.registerTimer('LoadJob', raise_if_registered=False)
        self.app.env.registerTimer('RenderFirstSubJob',
                                   raise_if_registered=False)
        self.app.env.registerTimer('BakeJob', raise_if_registered=False)

    def bake(self):
        logger.debug("  Bake Output: %s" % self.out_dir)
        logger.debug("  Root URL: %s" % self.app.config.get('site/root'))

        # Get into bake mode.
        start_time = time.perf_counter()
        self.app.config.set('baker/is_baking', True)
        self.app.env.base_asset_url_format = '%uri%'

        # Make sure the output directory exists.
        if not os.path.isdir(self.out_dir):
            os.makedirs(self.out_dir, 0o755)

        # Load/create the bake record.
        record = TransitionalBakeRecord()
        record_cache = self.app.cache.getCache('baker')
        record_id = hashlib.md5(self.out_dir.encode('utf8')).hexdigest()
        record_name = record_id + '.record'
        previous_record_path = None
        if not self.force and record_cache.has(record_name):
            with format_timed_scope(logger, "loaded previous bake record",
                                    level=logging.DEBUG, colored=False):
                previous_record_path = record_cache.getCachePath(record_name)
                record.loadPrevious(previous_record_path)
        record.current.success = True

        # Figure out if we need to clean the cache because important things
        # have changed.
        self._handleCacheValidity(record)

        # Pre-create all caches.
        for cache_name in ['app', 'baker', 'pages', 'renders']:
            self.app.cache.getCache(cache_name)

        # Gather all sources by realm -- we're going to bake each realm
        # separately so we can handle "overriding" (i.e. one realm overrides
        # another realm's pages, like the user realm overriding the theme
        # realm).
        sources_by_realm = {}
        for source in self.app.sources:
            srclist = sources_by_realm.setdefault(source.realm, [])
            srclist.append(source)

        # Create the worker processes.
        pool = self._createWorkerPool()

        # Bake the realms.
        realm_list = [REALM_USER, REALM_THEME]
        for realm in realm_list:
            srclist = sources_by_realm.get(realm)
            if srclist is not None:
                self._bakeRealm(record, pool, realm, srclist)

        # Bake taxonomies.
        self._bakeTaxonomies(record, pool)

        # All done with the workers.
        self._terminateWorkerPool(pool)

        # Get the timing information from the workers.
        record.current.timers = {}
        for i in range(len(pool.workers)):
            try:
                timers = pool.results.get(True, 0.1)
            except queue.Empty:
                logger.error("Didn't get timing information from all workers.")
                break

            worker_name = 'BakeWorker_%d' % i
            record.current.timers[worker_name] = {}
            for name, val in timers['data'].items():
                main_val = record.current.timers.setdefault(name, 0)
                record.current.timers[name] = main_val + val
                record.current.timers[worker_name][name] = val

        # Delete files from the output.
        self._handleDeletetions(record)

        # Backup previous records.
        for i in range(8, -1, -1):
            suffix = '' if i == 0 else '.%d' % i
            record_path = record_cache.getCachePath(
                    '%s%s.record' % (record_id, suffix))
            if os.path.exists(record_path):
                record_path_next = record_cache.getCachePath(
                        '%s.%s.record' % (record_id, i + 1))
                if os.path.exists(record_path_next):
                    os.remove(record_path_next)
                os.rename(record_path, record_path_next)

        # Save the bake record.
        with format_timed_scope(logger, "saved bake record.",
                                level=logging.DEBUG, colored=False):
            record.current.bake_time = time.time()
            record.current.out_dir = self.out_dir
            record.saveCurrent(record_cache.getCachePath(record_name))

        # All done.
        self.app.config.set('baker/is_baking', False)
        logger.debug(format_timed(start_time, 'done baking'))

        return record.detach()

    def _handleCacheValidity(self, record):
        start_time = time.perf_counter()

        reason = None
        if self.force:
            reason = "ordered to"
        elif not self.app.config.get('__cache_valid'):
            # The configuration file was changed, or we're running a new
            # version of the app.
            reason = "not valid anymore"
        elif (not record.previous.bake_time or
                not record.previous.hasLatestVersion()):
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
            if max_time >= record.previous.bake_time:
                reason = "templates modified"

        if reason is not None:
            # We have to bake everything from scratch.
            self.app.cache.clearCaches(except_names=['app'])
            self.force = True
            record.incremental_count = 0
            record.clearPrevious()
            logger.info(format_timed(
                    start_time,
                    "cleaned cache (reason: %s)" % reason))
        else:
            record.incremental_count += 1
            logger.debug(format_timed(
                    start_time, "cache is assumed valid",
                    colored=False))

    def _bakeRealm(self, record, pool, realm, srclist):
        start_time = time.perf_counter()
        try:
            record.current.baked_count[realm] = 0

            all_factories = []
            for source in srclist:
                factories = source.getPageFactories()
                all_factories += [f for f in factories
                                  if f.path not in self.taxonomy_pages]

            self._loadRealmPages(record, pool, all_factories)
            self._renderRealmPages(record, pool, all_factories)
            self._bakeRealmPages(record, pool, realm, all_factories)
        finally:
            page_count = record.current.baked_count[realm]
            logger.info(format_timed(
                    start_time,
                    "baked %d %s pages." %
                    (page_count, REALM_NAMES[realm].lower())))

    def _loadRealmPages(self, record, pool, factories):
        logger.debug("Loading %d realm pages..." % len(factories))
        with format_timed_scope(logger,
                                "loaded %d pages" % len(factories),
                                level=logging.DEBUG, colored=False,
                                timer_env=self.app.env,
                                timer_category='LoadJob'):
            for fac in factories:
                job = BakeWorkerJob(
                        JOB_LOAD,
                        LoadJobPayload(fac))
                pool.queue.put_nowait(job)

            def _handler(res):
                # Create the record entry for this page.
                record_entry = BakeRecordEntry(res.source_name, res.path)
                record_entry.config = res.config
                if res.errors:
                    record_entry.errors += res.errors
                    record.current.success = False
                    self._logErrors(res.path, res.errors)
                record.addEntry(record_entry)

            self._waitOnWorkerPool(
                    pool,
                    expected_result_count=len(factories),
                    result_handler=_handler)

    def _renderRealmPages(self, record, pool, factories):
        logger.debug("Rendering %d realm pages..." % len(factories))
        with format_timed_scope(logger,
                                "prepared %d pages" % len(factories),
                                level=logging.DEBUG, colored=False,
                                timer_env=self.app.env,
                                timer_category='RenderFirstSubJob'):
            expected_result_count = 0
            for fac in factories:
                record_entry = record.getCurrentEntry(fac.path)
                if record_entry.errors:
                    logger.debug("Ignoring %s because it had previous "
                                 "errors." % fac.ref_spec)
                    continue

                # Make sure the source and the route exist for this page,
                # otherwise we add errors to the record entry and we'll skip
                # this page for the rest of the bake.
                source = self.app.getSource(fac.source.name)
                if source is None:
                    record_entry.errors.append(
                            "Can't get source for page: %s" % fac.ref_spec)
                    logger.error(record_entry.errors[-1])
                    continue

                route = self.app.getRoute(fac.source.name, fac.metadata,
                                          skip_taxonomies=True)
                if route is None:
                    record_entry.errors.append(
                            "Can't get route for page: %s" % fac.ref_spec)
                    logger.error(record_entry.errors[-1])
                    continue

                # All good, queue the job.
                job = BakeWorkerJob(
                        JOB_RENDER_FIRST,
                        RenderFirstSubJobPayload(fac))
                pool.queue.put_nowait(job)
                expected_result_count += 1

            def _handler(res):
                entry = record.getCurrentEntry(res.path)
                if res.errors:
                    entry.errors += res.errors
                    record.current.success = False
                    self._logErrors(res.path, res.errors)

            self._waitOnWorkerPool(
                    pool,
                    expected_result_count=expected_result_count,
                    result_handler=_handler)

    def _bakeRealmPages(self, record, pool, realm, factories):
        logger.debug("Baking %d realm pages..." % len(factories))
        with format_timed_scope(logger,
                                "baked %d pages" % len(factories),
                                level=logging.DEBUG, colored=False,
                                timer_env=self.app.env,
                                timer_category='BakeJob'):
            expected_result_count = 0
            for fac in factories:
                if self._queueBakeJob(record, pool, fac):
                    expected_result_count += 1

            def _handler(res):
                entry = record.getCurrentEntry(res.path, res.taxonomy_info)
                entry.subs = res.sub_entries
                if res.errors:
                    entry.errors += res.errors
                    self._logErrors(res.path, res.errors)
                if entry.has_any_error:
                    record.current.success = False
                if entry.was_any_sub_baked:
                    record.current.baked_count[realm] += 1
                    record.dirty_source_names.add(entry.source_name)

            self._waitOnWorkerPool(
                    pool,
                    expected_result_count=expected_result_count,
                    result_handler=_handler)

    def _bakeTaxonomies(self, record, pool):
        logger.debug("Baking taxonomy pages...")
        with format_timed_scope(logger, 'built taxonomy buckets',
                                level=logging.DEBUG, colored=False):
            buckets = self._buildTaxonomyBuckets(record)

        start_time = time.perf_counter()
        page_count = self._bakeTaxonomyBuckets(record, pool, buckets)
        logger.info(format_timed(start_time,
                                 "baked %d taxonomy pages." % page_count))

    def _buildTaxonomyBuckets(self, record):
        # Let's see all the taxonomy terms for which we must bake a
        # listing page... first, pre-populate our big map of used terms.
        # For each source name, we have a list of taxonomies, and for each
        # taxonomies, a list of terms, some being 'dirty', some used last
        # time, etc.
        buckets = {}
        tax_names = [t.name for t in self.app.taxonomies]
        source_names = [s.name for s in self.app.sources]
        for sn in source_names:
            source_taxonomies = {}
            buckets[sn] = source_taxonomies
            for tn in tax_names:
                source_taxonomies[tn] = _TaxonomyTermsInfo()

        # Now see which ones are 'dirty' based on our bake record.
        logger.debug("Gathering dirty taxonomy terms")
        for prev_entry, cur_entry in record.transitions.values():
            # Re-bake all taxonomy pages that include new or changed
            # pages.
            if cur_entry and cur_entry.was_any_sub_baked:
                entries = [cur_entry]
                if prev_entry:
                    entries.append(prev_entry)

                for tax in self.app.taxonomies:
                    changed_terms = set()
                    for e in entries:
                        terms = e.config.get(tax.setting_name)
                        if terms:
                            if not tax.is_multiple:
                                terms = [terms]
                            changed_terms |= set(terms)

                    if len(changed_terms) > 0:
                        tt_info = buckets[cur_entry.source_name][tax.name]
                        tt_info.dirty_terms |= changed_terms

            # Remember all terms used.
            for tax in self.app.taxonomies:
                if cur_entry and not cur_entry.was_overriden:
                    cur_terms = cur_entry.config.get(tax.setting_name)
                    if cur_terms:
                        if not tax.is_multiple:
                            cur_terms = [cur_terms]
                        tt_info = buckets[cur_entry.source_name][tax.name]
                        tt_info.all_terms |= set(cur_terms)

        # Re-bake the combination pages for terms that are 'dirty'.
        known_combinations = set()
        logger.debug("Gathering dirty term combinations")
        for prev_entry, cur_entry in record.transitions.values():
            if not cur_entry:
                continue
            used_taxonomy_terms = cur_entry.getAllUsedTaxonomyTerms()
            for sn, tn, terms in used_taxonomy_terms:
                if isinstance(terms, tuple):
                    known_combinations.add((sn, tn, terms))
        for sn, tn, terms in known_combinations:
            tt_info = buckets[sn][tn]
            tt_info.all_terms.add(terms)
            if not tt_info.dirty_terms.isdisjoint(set(terms)):
                tt_info.dirty_terms.add(terms)

        return buckets

    def _bakeTaxonomyBuckets(self, record, pool, buckets):
        # Start baking those terms.
        expected_result_count = 0
        for source_name, source_taxonomies in buckets.items():
            for tax_name, tt_info in source_taxonomies.items():
                terms = tt_info.dirty_terms
                if len(terms) == 0:
                    continue

                logger.debug(
                        "Baking '%s' for source '%s': %s" %
                        (tax_name, source_name, terms))
                tax = self.app.getTaxonomy(tax_name)
                source = self.app.getSource(source_name)
                tax_page_ref = tax.getPageRef(source)
                if not tax_page_ref.exists:
                    logger.debug(
                            "No taxonomy page found at '%s', skipping." %
                            tax.page_ref)
                    continue

                logger.debug(
                        "Using taxonomy page: %s:%s" %
                        (tax_page_ref.source_name, tax_page_ref.rel_path))
                fac = tax_page_ref.getFactory()

                for term in terms:
                    logger.debug(
                            "Queuing: %s [%s=%s]" %
                            (fac.ref_spec, tax_name, term))
                    tax_info = TaxonomyInfo(tax_name, source_name, term)

                    cur_entry = BakeRecordEntry(
                            fac.source.name, fac.path, tax_info)
                    record.addEntry(cur_entry)

                    if self._queueBakeJob(record, pool, fac, tax_info):
                        expected_result_count += 1

        def _handler(res):
            entry = record.getCurrentEntry(res.path, res.taxonomy_info)
            entry.subs = res.sub_entries
            if res.errors:
                entry.errors += res.errors
            if entry.has_any_error:
                record.current.success = False

        self._waitOnWorkerPool(
                pool,
                expected_result_count=expected_result_count,
                result_handler=_handler)

        # Now we create bake entries for all the terms that were *not* dirty.
        # This is because otherwise, on the next incremental bake, we wouldn't
        # find any entry for those things, and figure that we need to delete
        # their outputs.
        for prev_entry, cur_entry in record.transitions.values():
            # Only consider taxonomy-related entries that don't have any
            # current version.
            if (prev_entry and prev_entry.taxonomy_info and
                    not cur_entry):
                ti = prev_entry.taxonomy_info
                tt_info = buckets[ti.source_name][ti.taxonomy_name]
                if ti.term in tt_info.all_terms:
                    logger.debug("Creating unbaked entry for taxonomy "
                                 "term '%s:%s'." % (ti.taxonomy_name, ti.term))
                    record.collapseEntry(prev_entry)
                else:
                    logger.debug("Taxonomy term '%s:%s' isn't used anymore." %
                                 (ti.taxonomy_name, ti.term))

        return expected_result_count

    def _queueBakeJob(self, record, pool, fac, tax_info=None):
        # Get the previous (if any) and current entry for this page.
        pair = record.getPreviousAndCurrentEntries(fac.path, tax_info)
        assert pair is not None
        prev_entry, cur_entry = pair
        assert cur_entry is not None

        # Ignore if there were errors in the previous passes.
        if cur_entry.errors:
            logger.debug("Ignoring %s because it had previous "
                         "errors." % fac.ref_spec)
            return False

        # Build the route metadata and find the appropriate route.
        route_metadata = copy.deepcopy(fac.metadata)
        if tax_info is not None:
            tax = self.app.getTaxonomy(tax_info.taxonomy_name)
            route = self.app.getTaxonomyRoute(tax_info.taxonomy_name,
                                              tax_info.source_name)

            slugified_term = route.slugifyTaxonomyTerm(tax_info.term)
            route_metadata[tax.term_name] = slugified_term
        else:
            route = self.app.getRoute(fac.source.name, route_metadata,
                                      skip_taxonomies=True)
        assert route is not None

        # Figure out if this page is overriden by another previously
        # baked page. This happens for example when the user has
        # made a page that has the same page/URL as a theme page.
        page = fac.buildPage()
        uri = route.getUri(route_metadata, provider=page)
        override_entry = record.getOverrideEntry(page.path, uri)
        if override_entry is not None:
            override_source = self.app.getSource(
                    override_entry.source_name)
            if override_source.realm == fac.source.realm:
                cur_entry.errors.append(
                        "Page '%s' maps to URL '%s' but is overriden "
                        "by page '%s'." %
                        (fac.ref_spec, uri, override_entry.path))
                logger.error(cur_entry.errors[-1])
            cur_entry.flags |= BakeRecordEntry.FLAG_OVERRIDEN
            return False

        job = BakeWorkerJob(
                JOB_BAKE,
                BakeJobPayload(fac, route_metadata, prev_entry,
                               record.dirty_source_names,
                               tax_info))
        pool.queue.put_nowait(job)
        return True

    def _handleDeletetions(self, record):
        logger.debug("Handling deletions...")
        for path, reason in record.getDeletions():
            logger.debug("Removing '%s': %s" % (path, reason))
            try:
                os.remove(path)
                logger.info('[delete] %s' % path)
            except OSError:
                # Not a big deal if that file had already been removed
                # by the user.
                pass

    def _logErrors(self, path, errors):
        rel_path = os.path.relpath(path, self.app.root_dir)
        logger.error("Errors found in %s:" % rel_path)
        for e in errors:
            logger.error("  " + e)

    def _createWorkerPool(self):
        import sys
        from piecrust.baking.worker import BakeWorkerContext, worker_func

        main_module = sys.modules['__main__']
        is_profiling = os.path.basename(main_module.__file__) in [
                'profile.py', 'cProfile.py']

        pool = _WorkerPool()
        for i in range(self.num_workers):
            ctx = BakeWorkerContext(
                    self.app.root_dir, self.app.cache.base_dir, self.out_dir,
                    pool.queue, pool.results, pool.abort_event,
                    force=self.force, debug=self.app.debug,
                    is_profiling=is_profiling)
            w = multiprocessing.Process(
                    name='BakeWorker_%d' % i,
                    target=worker_func, args=(i, ctx))
            w.start()
            pool.workers.append(w)
        return pool

    def _terminateWorkerPool(self, pool):
        pool.abort_event.set()
        for w in pool.workers:
            w.join()

    def _waitOnWorkerPool(self, pool,
                          expected_result_count=-1, result_handler=None):
        assert result_handler is None or expected_result_count >= 0
        abort_with_exception = None
        try:
            if result_handler is None:
                pool.queue.join()
            else:
                got_count = 0
                while got_count < expected_result_count:
                    try:
                        res = pool.results.get(True, 10)
                    except queue.Empty:
                        logger.error(
                                "Got %d results, expected %d, and timed-out "
                                "for 10 seconds. A worker might be stuck?" %
                                (got_count, expected_result_count))
                        abort_with_exception = Exception("Worker time-out.")
                        break

                    if isinstance(res, dict) and res.get('type') == 'error':
                        abort_with_exception = Exception(
                                'Worker critical error:\n' +
                                '\n'.join(res['messages']))
                        break

                    got_count += 1
                    result_handler(res)
        except KeyboardInterrupt as kiex:
            logger.warning("Bake aborted by user... "
                           "waiting for workers to stop.")
            abort_with_exception = kiex

        if abort_with_exception:
            pool.abort_event.set()
            for w in pool.workers:
                w.join(2)
            raise abort_with_exception


class _WorkerPool(object):
    def __init__(self):
        self.queue = multiprocessing.JoinableQueue()
        self.results = multiprocessing.Queue()
        self.abort_event = multiprocessing.Event()
        self.workers = []


class _TaxonomyTermsInfo(object):
    def __init__(self):
        self.dirty_terms = set()
        self.all_terms = set()

    def __str__(self):
        return 'dirty:%s, all:%s' % (self.dirty_terms, self.all_terms)

    def __repr__(self):
        return 'dirty:%s, all:%s' % (self.dirty_terms, self.all_terms)

