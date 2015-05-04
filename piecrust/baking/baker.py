import time
import os.path
import hashlib
import logging
import threading
from piecrust.baking.records import (
        TransitionalBakeRecord, BakeRecordPageEntry)
from piecrust.baking.scheduler import BakeScheduler
from piecrust.baking.single import (BakingError, PageBaker)
from piecrust.chefutil import format_timed, log_friendly_exception
from piecrust.sources.base import (
        REALM_NAMES, REALM_USER, REALM_THEME)


logger = logging.getLogger(__name__)


class Baker(object):
    def __init__(self, app, out_dir, force=False):
        assert app and out_dir
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.num_workers = app.config.get('baker/workers', 4)

        # Remember what taxonomy pages we should skip
        # (we'll bake them repeatedly later with each taxonomy term)
        self.taxonomy_pages = []
        logger.debug("Gathering taxonomy page paths:")
        for tax in self.app.taxonomies:
            for src in self.app.sources:
                path = tax.resolvePagePath(src.name)
                if path is not None:
                    self.taxonomy_pages.append(path)
                    logger.debug(" - %s" % path)

    def bake(self):
        logger.debug("  Bake Output: %s" % self.out_dir)
        logger.debug("  Root URL: %s" % self.app.config.get('site/root'))

        # Get into bake mode.
        start_time = time.clock()
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
        if not self.force and record_cache.has(record_name):
            t = time.clock()
            record.loadPrevious(record_cache.getCachePath(record_name))
            logger.debug(format_timed(
                    t, 'loaded previous bake record',
                    colored=False))
        record.current.success = True

        # Figure out if we need to clean the cache because important things
        # have changed.
        self._handleCacheValidity(record)

        # Gather all sources by realm -- we're going to bake each realm
        # separately so we can handle "overlaying" (i.e. one realm overrides
        # another realm's pages).
        sources_by_realm = {}
        for source in self.app.sources:
            srclist = sources_by_realm.setdefault(source.realm, [])
            srclist.append(source)

        # Bake the realms.
        realm_list = [REALM_USER, REALM_THEME]
        for realm in realm_list:
            srclist = sources_by_realm.get(realm)
            if srclist is not None:
                self._bakeRealm(record, realm, srclist)

        # Bake taxonomies.
        self._bakeTaxonomies(record)

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
        t = time.clock()
        record.current.bake_time = time.time()
        record.current.out_dir = self.out_dir
        record.saveCurrent(record_cache.getCachePath(record_name))
        logger.debug(format_timed(t, 'saved bake record', colored=False))

        # All done.
        self.app.config.set('baker/is_baking', False)
        logger.debug(format_timed(start_time, 'done baking'))

        return record.detach()

    def _handleCacheValidity(self, record):
        start_time = time.clock()

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

    def _bakeRealm(self, record, realm, srclist):
        # Gather all page factories from the sources and queue them
        # for the workers to pick up. Just skip taxonomy pages for now.
        logger.debug("Baking realm %s" % REALM_NAMES[realm])
        pool, queue, abort = self._createWorkerPool(record, self.num_workers)

        for source in srclist:
            factories = source.getPageFactories()
            for fac in factories:
                if fac.path in self.taxonomy_pages:
                    logger.debug(
                            "Skipping taxonomy page: %s:%s" %
                            (source.name, fac.ref_spec))
                    continue

                entry = BakeRecordPageEntry(fac.source.name, fac.rel_path,
                                            fac.path)
                record.addEntry(entry)

                route = self.app.getRoute(source.name, fac.metadata,
                                          skip_taxonomies=True)
                if route is None:
                    entry.errors.append(
                            "Can't get route for page: %s" % fac.ref_spec)
                    logger.error(entry.errors[-1])
                    continue

                queue.addJob(BakeWorkerJob(fac, route, entry))

        success = self._waitOnWorkerPool(pool, abort)
        record.current.success &= success

    def _bakeTaxonomies(self, record):
        logger.debug("Baking taxonomies")

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

        # Start baking those terms.
        pool, queue, abort = self._createWorkerPool(record, self.num_workers)
        for source_name, source_taxonomies in buckets.items():
            for tax_name, tt_info in source_taxonomies.items():
                terms = tt_info.dirty_terms
                if len(terms) == 0:
                    continue

                logger.debug(
                        "Baking '%s' for source '%s': %s" %
                        (tax_name, source_name, terms))
                tax = self.app.getTaxonomy(tax_name)
                route = self.app.getTaxonomyRoute(tax_name, source_name)
                tax_page_ref = tax.getPageRef(source_name)
                if not tax_page_ref.exists:
                    logger.debug(
                            "No taxonomy page found at '%s', skipping." %
                            tax.page_ref)
                    continue

                logger.debug(
                        "Using taxonomy page: %s:%s" %
                        (tax_page_ref.source_name, tax_page_ref.rel_path))
                for term in terms:
                    fac = tax_page_ref.getFactory()
                    logger.debug(
                            "Queuing: %s [%s=%s]" %
                            (fac.ref_spec, tax_name, term))
                    entry = BakeRecordPageEntry(
                            fac.source.name, fac.rel_path, fac.path,
                            (tax_name, term, source_name))
                    record.addEntry(entry)
                    queue.addJob(BakeWorkerJob(fac, route, entry))

        success = self._waitOnWorkerPool(pool, abort)
        record.current.success &= success

        # Now we create bake entries for all the terms that were *not* dirty.
        # This is because otherwise, on the next incremental bake, we wouldn't
        # find any entry for those things, and figure that we need to delete
        # their outputs.
        for prev_entry, cur_entry in record.transitions.values():
            # Only consider taxonomy-related entries that don't have any
            # current version.
            if (prev_entry and prev_entry.taxonomy_info and
                    not cur_entry):
                sn = prev_entry.source_name
                tn, tt, tsn = prev_entry.taxonomy_info
                tt_info = buckets[tsn][tn]
                if tt in tt_info.all_terms:
                    logger.debug("Creating unbaked entry for taxonomy "
                                 "term '%s:%s'." % (tn, tt))
                    record.collapseEntry(prev_entry)
                else:
                    logger.debug("Taxonomy term '%s:%s' isn't used anymore." %
                                 (tn, tt))

    def _handleDeletetions(self, record):
        for path, reason in record.getDeletions():
            logger.debug("Removing '%s': %s" % (path, reason))
            try:
                os.remove(path)
                logger.info('[delete] %s' % path)
            except OSError:
                # Not a big deal if that file had already been removed
                # by the user.
                pass

    def _createWorkerPool(self, record, pool_size=4):
        pool = []
        queue = BakeScheduler(record)
        abort = threading.Event()
        for i in range(pool_size):
            ctx = BakeWorkerContext(
                    self.app, self.out_dir, self.force,
                    record, queue, abort)
            worker = BakeWorker(i, ctx)
            pool.append(worker)
        return pool, queue, abort

    def _waitOnWorkerPool(self, pool, abort):
        for w in pool:
            w.start()

        success = True
        try:
            for w in pool:
                w.join()
                success &= w.success
        except KeyboardInterrupt:
            logger.warning("Bake aborted by user... "
                           "waiting for workers to stop.")
            abort.set()
            for w in pool:
                w.join()
            raise

        if abort.is_set():
            excs = [w.abort_exception for w in pool
                    if w.abort_exception is not None]
            logger.error("Baking was aborted due to %s error(s):" % len(excs))
            if self.app.debug:
                for e in excs:
                    logger.exception(e)
            else:
                for e in excs:
                    log_friendly_exception(logger, e)
            raise BakingError("Baking was aborted due to errors.")

        return success


class BakeWorkerContext(object):
    def __init__(self, app, out_dir, force, record, work_queue,
                 abort_event):
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.record = record
        self.work_queue = work_queue
        self.abort_event = abort_event


class BakeWorkerJob(object):
    def __init__(self, factory, route, record_entry):
        self.factory = factory
        self.route = route
        self.record_entry = record_entry

    @property
    def source(self):
        return self.factory.source


class BakeWorker(threading.Thread):
    def __init__(self, wid, ctx):
        super(BakeWorker, self).__init__(name=('worker%d' % wid))
        self.wid = wid
        self.ctx = ctx
        self.abort_exception = None
        self.success = True
        self._page_baker = PageBaker(
                ctx.app, ctx.out_dir, ctx.force,
                ctx.record)

    def run(self):
        while(not self.ctx.abort_event.is_set()):
            try:
                job = self.ctx.work_queue.getNextJob(wait_timeout=1)
                if job is None:
                    logger.debug(
                            "[%d] No more work... shutting down." %
                            self.wid)
                    break
                success = self._unsafeRun(job)
                logger.debug("[%d] Done with page." % self.wid)
                self.ctx.work_queue.onJobFinished(job)
                self.success &= success
            except Exception as ex:
                self.ctx.abort_event.set()
                self.abort_exception = ex
                self.success = False
                logger.debug("[%d] Critical error, aborting." % self.wid)
                if self.ctx.app.debug:
                    logger.exception(ex)
                break

    def _unsafeRun(self, job):
        start_time = time.clock()

        entry = job.record_entry
        try:
            self._page_baker.bake(job.factory, job.route, entry)
        except BakingError as ex:
            logger.debug("Got baking error. Adding it to the record.")
            while ex:
                entry.errors.append(str(ex))
                ex = ex.__cause__

        has_error = False
        for e in entry.getAllErrors():
            has_error = True
            logger.error(e)
        if has_error:
            return False

        if entry.was_any_sub_baked:
            first_sub = entry.subs[0]

            friendly_uri = first_sub.out_uri
            if friendly_uri == '':
                friendly_uri = '[main page]'

            friendly_count = ''
            if entry.num_subs > 1:
                friendly_count = ' (%d pages)' % entry.num_subs
            logger.info(format_timed(
                    start_time, '[%d] %s%s' %
                    (self.wid, friendly_uri, friendly_count)))

        return True


class _TaxonomyTermsInfo(object):
    def __init__(self):
        self.dirty_terms = set()
        self.all_terms = set()

    def __str__(self):
        return 'dirty:%s, all:%s' % (self.dirty_terms, self.all_terms)

    def __repr__(self):
        return 'dirty:%s, all:%s' % (self.dirty_terms, self.all_terms)
