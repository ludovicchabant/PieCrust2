import time
import os.path
import hashlib
import logging
from piecrust.baking.records import (
        BakeRecordEntry, TransitionalBakeRecord, TaxonomyInfo)
from piecrust.baking.worker import (
        save_factory,
        JOB_LOAD, JOB_RENDER_FIRST, JOB_BAKE)
from piecrust.chefutil import (
        format_timed_scope, format_timed)
from piecrust.routing import create_route_metadata
from piecrust.sources.base import (
        REALM_NAMES, REALM_USER, REALM_THEME)


logger = logging.getLogger(__name__)


class Baker(object):
    def __init__(self, app, out_dir, force=False,
                 applied_config_variant=None,
                 applied_config_values=None):
        assert app and out_dir
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.applied_config_variant = applied_config_variant
        self.applied_config_values = applied_config_values

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
        is_cache_valid = self._handleCacheValidity(record)
        if not is_cache_valid:
            previous_record_path = None

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
        pool = self._createWorkerPool(previous_record_path)

        # Bake the realms.
        realm_list = [REALM_USER, REALM_THEME]
        for realm in realm_list:
            srclist = sources_by_realm.get(realm)
            if srclist is not None:
                self._bakeRealm(record, pool, realm, srclist)

        # Bake taxonomies.
        self._bakeTaxonomies(record, pool)

        # All done with the workers. Close the pool and get timing reports.
        reports = pool.close()
        record.current.timers = {}
        for i in range(len(reports)):
            timers = reports[i]
            if timers is None:
                continue

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
            return False
        else:
            record.incremental_count += 1
            logger.debug(format_timed(
                    start_time, "cache is assumed valid",
                    colored=False))
            return True

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
        def _handler(res):
            # Create the record entry for this page.
            # This will also update the `dirty_source_names` for the record
            # as we add page files whose last modification times are later
            # than the last bake.
            record_entry = BakeRecordEntry(res['source_name'], res['path'])
            record_entry.config = res['config']
            if res['errors']:
                record_entry.errors += res['errors']
                record.current.success = False
                self._logErrors(res['path'], res['errors'])
            record.addEntry(record_entry)

        logger.debug("Loading %d realm pages..." % len(factories))
        with format_timed_scope(logger,
                                "loaded %d pages" % len(factories),
                                level=logging.DEBUG, colored=False,
                                timer_env=self.app.env,
                                timer_category='LoadJob'):
            jobs = []
            for fac in factories:
                job = {
                        'type': JOB_LOAD,
                        'job': save_factory(fac)}
                jobs.append(job)
            ar = pool.queueJobs(jobs, handler=_handler)
            ar.wait()

    def _renderRealmPages(self, record, pool, factories):
        def _handler(res):
            entry = record.getCurrentEntry(res['path'])
            if res['errors']:
                entry.errors += res['errors']
                record.current.success = False
                self._logErrors(res['path'], res['errors'])

        logger.debug("Rendering %d realm pages..." % len(factories))
        with format_timed_scope(logger,
                                "prepared %d pages" % len(factories),
                                level=logging.DEBUG, colored=False,
                                timer_env=self.app.env,
                                timer_category='RenderFirstSubJob'):
            jobs = []
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
                job = {
                        'type': JOB_RENDER_FIRST,
                        'job': save_factory(fac)}
                jobs.append(job)

            ar = pool.queueJobs(jobs, handler=_handler)
            ar.wait()

    def _bakeRealmPages(self, record, pool, realm, factories):
        def _handler(res):
            entry = record.getCurrentEntry(res['path'], res['taxonomy_info'])
            entry.subs = res['sub_entries']
            if res['errors']:
                entry.errors += res['errors']
                self._logErrors(res['path'], res['errors'])
            if entry.has_any_error:
                record.current.success = False
            if entry.subs and entry.was_any_sub_baked:
                record.current.baked_count[realm] += 1

        logger.debug("Baking %d realm pages..." % len(factories))
        with format_timed_scope(logger,
                                "baked %d pages" % len(factories),
                                level=logging.DEBUG, colored=False,
                                timer_env=self.app.env,
                                timer_category='BakeJob'):
            jobs = []
            for fac in factories:
                job = self._makeBakeJob(record, fac)
                if job is not None:
                    jobs.append(job)

            ar = pool.queueJobs(jobs, handler=_handler)
            ar.wait()

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
        def _handler(res):
            entry = record.getCurrentEntry(res['path'], res['taxonomy_info'])
            entry.subs = res['sub_entries']
            if res['errors']:
                entry.errors += res['errors']
            if entry.has_any_error:
                record.current.success = False

        # Start baking those terms.
        jobs = []
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

                    job = self._makeBakeJob(record, fac, tax_info)
                    if job is not None:
                        jobs.append(job)

        ar = pool.queueJobs(jobs, handler=_handler)
        ar.wait()

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

        return len(jobs)

    def _makeBakeJob(self, record, fac, tax_info=None):
        # Get the previous (if any) and current entry for this page.
        pair = record.getPreviousAndCurrentEntries(fac.path, tax_info)
        assert pair is not None
        prev_entry, cur_entry = pair
        assert cur_entry is not None

        # Ignore if there were errors in the previous passes.
        if cur_entry.errors:
            logger.debug("Ignoring %s because it had previous "
                         "errors." % fac.ref_spec)
            return None

        # Build the route metadata and find the appropriate route.
        page = fac.buildPage()
        route_metadata = create_route_metadata(page)
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
        uri = route.getUri(route_metadata)
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
            return None

        job = {
                'type': JOB_BAKE,
                'job': {
                        'factory_info': save_factory(fac),
                        'taxonomy_info': tax_info,
                        'route_metadata': route_metadata,
                        'dirty_source_names': record.dirty_source_names
                        }
                }
        return job

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

    def _createWorkerPool(self, previous_record_path):
        from piecrust.app import PieCrustFactory
        from piecrust.workerpool import WorkerPool
        from piecrust.baking.worker import BakeWorkerContext, BakeWorker

        appfactory = PieCrustFactory(
                self.app.root_dir,
                cache=self.app.cache.enabled,
                cache_key=self.app.cache_key,
                config_variant=self.applied_config_variant,
                config_values=self.applied_config_values,
                debug=self.app.debug,
                theme_site=self.app.theme_site)

        worker_count = self.app.config.get('baker/workers')
        batch_size = self.app.config.get('baker/batch_size')

        ctx = BakeWorkerContext(
                appfactory,
                self.out_dir,
                force=self.force,
                previous_record_path=previous_record_path)
        pool = WorkerPool(
                worker_count=worker_count,
                batch_size=batch_size,
                worker_class=BakeWorker,
                initargs=(ctx,))
        return pool


class _TaxonomyTermsInfo(object):
    def __init__(self):
        self.dirty_terms = set()
        self.all_terms = set()

    def __str__(self):
        return 'dirty:%s, all:%s' % (self.dirty_terms, self.all_terms)

    def __repr__(self):
        return 'dirty:%s, all:%s' % (self.dirty_terms, self.all_terms)

