import time
import os.path
import shutil
import hashlib
import logging
import threading
from piecrust.baking.records import (
        TransitionalBakeRecord, BakeRecordPageEntry)
from piecrust.baking.scheduler import BakeScheduler
from piecrust.baking.single import (BakingError, PageBaker)
from piecrust.chefutil import format_timed, log_friendly_exception
from piecrust.sources.base import (
        PageFactory,
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
        record_name = (
                hashlib.md5(self.out_dir.encode('utf8')).hexdigest() +
                '.record')
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

        # Save the bake record.
        t = time.clock()
        record.current.bake_time = time.time()
        record.current.out_dir = self.out_dir
        record.collapseRecords()
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
            for cache_name in self.app.cache.getCacheNames(
                    except_names=['app']):
                cache_dir = self.app.cache.getCacheDir(cache_name)
                if os.path.isdir(cache_dir):
                    logger.debug("Cleaning baker cache: %s" % cache_dir)
                    shutil.rmtree(cache_dir)
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

                entry = BakeRecordPageEntry(fac)
                record.addEntry(entry)

                route = self.app.getRoute(source.name, fac.metadata)
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
        buckets = {}
        tax_names = [t.name for t in self.app.taxonomies]
        source_names = [s.name for s in self.app.sources]
        for sn in source_names:
            source_taxonomies = {}
            buckets[sn] = source_taxonomies
            for tn in tax_names:
                source_taxonomies[tn] = set()

        # Now see which ones are 'dirty' based on our bake record.
        logger.debug("Gathering dirty taxonomy terms")
        for prev_entry, cur_entry in record.transitions.values():
            for tax in self.app.taxonomies:
                changed_terms = None
                # Re-bake all taxonomy pages that include new or changed
                # pages.
                if (not prev_entry and cur_entry and
                        cur_entry.was_baked_successfully):
                    changed_terms = cur_entry.config.get(tax.setting_name)
                elif (prev_entry and cur_entry and
                        cur_entry.was_baked_successfully):
                    changed_terms = []
                    prev_terms = prev_entry.config.get(tax.setting_name)
                    cur_terms = cur_entry.config.get(tax.setting_name)
                    if tax.is_multiple:
                        if prev_terms is not None:
                            changed_terms += prev_terms
                        if cur_terms is not None:
                            changed_terms += cur_terms
                    else:
                        if prev_terms is not None:
                            changed_terms.append(prev_terms)
                        if cur_terms is not None:
                            changed_terms.append(cur_terms)
                if changed_terms is not None:
                    if not isinstance(changed_terms, list):
                        changed_terms = [changed_terms]
                    buckets[cur_entry.source_name][tax.name] |= (
                            set(changed_terms))

        # Re-bake the combination pages for terms that are 'dirty'.
        known_combinations = set()
        logger.debug("Gathering dirty term combinations")
        for prev_entry, cur_entry in record.transitions.values():
            if cur_entry:
                known_combinations |= cur_entry.used_taxonomy_terms
            elif prev_entry:
                known_combinations |= prev_entry.used_taxonomy_terms
        for sn, tn, terms in known_combinations:
            changed_terms = buckets[sn][tn]
            if not changed_terms.isdisjoint(set(terms)):
                changed_terms.add(terms)

        # Start baking those terms.
        pool, queue, abort = self._createWorkerPool(record, self.num_workers)
        for source_name, source_taxonomies in buckets.items():
            for tax_name, terms in source_taxonomies.items():
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

                tax_page_source = tax_page_ref.source
                tax_page_rel_path = tax_page_ref.rel_path
                logger.debug(
                        "Using taxonomy page: %s:%s" %
                        (tax_page_source.name, tax_page_rel_path))

                for term in terms:
                    fac = PageFactory(
                            tax_page_source, tax_page_rel_path,
                            {tax.term_name: term})
                    logger.debug(
                            "Queuing: %s [%s, %s]" %
                            (fac.ref_spec, tax_name, term))
                    entry = BakeRecordPageEntry(fac, tax_name, term)
                    record.addEntry(entry)
                    queue.addJob(
                            BakeWorkerJob(fac, route, entry, tax_name, term))

        success = self._waitOnWorkerPool(pool, abort)
        record.current.success &= success

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
    def __init__(self, factory, route, record_entry,
                 taxonomy_name=None, taxonomy_term=None):
        self.factory = factory
        self.route = route
        self.record_entry = record_entry
        self.taxonomy_name = taxonomy_name
        self.taxonomy_term = taxonomy_term

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
            self._page_baker.bake(
                    job.factory, job.route, entry,
                    taxonomy_name=job.taxonomy_name,
                    taxonomy_term=job.taxonomy_term)
        except BakingError as ex:
            logger.debug("Got baking error. Adding it to the record.")
            while ex:
                entry.errors.append(str(ex))
                ex = ex.__cause__

        if entry.errors:
            for e in entry.errors:
                logger.error(e)
            return False

        if entry.was_baked_successfully:
            uri = entry.out_uris[0]
            friendly_uri = uri if uri != '' else '[main page]'
            friendly_count = ''
            if entry.num_subs > 1:
                friendly_count = ' (%d pages)' % entry.num_subs
            logger.info(format_timed(
                    start_time, '[%d] %s%s' %
                    (self.wid, friendly_uri, friendly_count)))

        return True

