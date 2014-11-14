import time
import os.path
import codecs
import shutil
import hashlib
import logging
import threading
import urllib.request, urllib.error, urllib.parse
from piecrust.baking.records import (TransitionalBakeRecord,
        BakeRecordPageEntry,
        FLAG_OVERRIDEN, FLAG_SOURCE_MODIFIED)
from piecrust.chefutil import format_timed, log_friendly_exception
from piecrust.data.filters import (PaginationFilter, HasFilterClause,
        IsFilterClause, AndBooleanClause)
from piecrust.rendering import (PageRenderingContext, render_page,
        PASS_FORMATTING, PASS_RENDERING)
from piecrust.sources.base import (PageFactory,
        REALM_NAMES, REALM_USER, REALM_THEME)


logger = logging.getLogger(__name__)


class BakingError(Exception):
    pass


class PageBaker(object):
    def __init__(self, app, out_dir, force=False, record=None,
            copy_assets=True):
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.record = record
        self.copy_assets = copy_assets
        self.site_root = app.config.get('site/root')
        self.pretty_urls = app.config.get('site/pretty_urls')
        self.pagination_suffix = app.config.get('site/pagination_suffix')

    def getOutputUri(self, uri, num):
        suffix = self.pagination_suffix.replace('%num%', str(num))
        if self.pretty_urls:
            # Output will be:
            # - `uri/name`
            # - `uri/name/2`
            # - `uri/name.ext`
            # - `uri/name.ext/2`
            if num <= 1:
                return uri
            return uri + suffix
        else:
            # Output will be:
            # - `uri/name.html`
            # - `uri/name/2.html`
            # - `uri/name.ext`
            # - `uri/name/2.ext`
            if uri == '/':
                if num <= 1:
                    return '/'
                return '/' + suffix.lstrip('/')
            else:
                if num <= 1:
                    return uri
                #TODO: watch out for tags with dots in them.
                base_uri, ext = os.path.splitext(uri)
                return base_uri + suffix + ext

    def getOutputPath(self, uri):
        bake_path = [self.out_dir]
        decoded_uri = urllib.parse.unquote(uri.lstrip('/'))
        if self.pretty_urls:
            bake_path.append(decoded_uri)
            bake_path.append('index.html')
        else:
            name, ext = os.path.splitext(decoded_uri)
            if decoded_uri == '':
                bake_path.append('index.html')
            elif ext:
                bake_path.append(decoded_uri)
            else:
                bake_path.append(decoded_uri + '.html')

        return os.path.normpath(os.path.join(*bake_path))

    def bake(self, factory, route, record_entry,
            taxonomy_name=None, taxonomy_term=None):
        pagination_filter = None
        custom_data = None
        if taxonomy_name and taxonomy_term:
            # Must bake a taxonomy listing page... we'll have to add a
            # pagination filter for only get matching posts, and the output
            # URL will be a bit different.
            tax = self.app.getTaxonomy(taxonomy_name)
            pagination_filter = PaginationFilter()
            if tax.is_multiple:
                if isinstance(taxonomy_term, tuple):
                    abc = AndBooleanClause()
                    for t in taxonomy_term:
                        abc.addClause(HasFilterClause(taxonomy_name, t))
                    pagination_filter.addClause(abc)
                    slugified_term = '/'.join(taxonomy_term)
                else:
                    pagination_filter.addClause(HasFilterClause(taxonomy_name,
                            taxonomy_term))
                    slugified_term = taxonomy_term
            else:
                pagination_filter.addClause(IsFilterClause(taxonomy_name,
                        taxonomy_term))
                slugified_term = taxonomy_term
            custom_data = {tax.term_name: taxonomy_term}
            uri = route.getUri({tax.term_name: slugified_term})
        else:
            # Normal page bake.
            uri = route.getUri(factory.metadata)

        override = self.record.getOverrideEntry(factory, uri)
        if override is not None:
            override_source = self.app.getSource(override.source_name)
            if override_source.realm == factory.source.realm:
                raise BakingError(
                        "Page '%s' maps to URL '%s' but is overriden by page"
                        "'%s:%s'." % (factory.ref_spec, uri,
                            override.source_name, override.rel_path))
            logger.debug("'%s' [%s] is overriden by '%s:%s'. Skipping" %
                    (factory.ref_spec, uri, override.source_name,
                        override.rel_path))
            record_entry.flags |= FLAG_OVERRIDEN
            return

        cur_sub = 1
        has_more_subs = True
        force_this = self.force
        invalidate_formatting = False
        page = factory.buildPage()
        record_entry.config = page.config.get().copy()
        prev_record_entry = self.record.getPreviousEntry(
                factory.source.name, factory.rel_path,
                taxonomy_name, taxonomy_term)

        logger.debug("Baking '%s'..." % uri)

        # If the current page is known to use pages from other sources,
        # see if any of those got baked, or are going to be baked for some
        # reason. If so, we need to bake this one too.
        # (this happens for instance with the main page of a blog).
        if prev_record_entry and prev_record_entry.was_baked_successfully:
            invalidated_render_passes = set()
            used_src_names = list(prev_record_entry.used_source_names)
            for src_name, rdr_pass in used_src_names:
                entries = self.record.getCurrentEntries(src_name)
                for e in entries:
                    if e.was_baked or e.flags & FLAG_SOURCE_MODIFIED:
                        invalidated_render_passes.add(rdr_pass)
                        break
            if len(invalidated_render_passes) > 0:
                logger.debug("'%s' is known to use sources %s, at least one "
                             "of which got baked. Will force bake this page. "
                             % (uri, used_src_names))
                force_this = True
                if PASS_FORMATTING in invalidated_render_passes:
                    logger.debug("Will invalidate cached formatting for '%s' "
                                 "since sources were using during that pass."
                                 % uri)
                    invalidate_formatting = True

        while has_more_subs:
            sub_uri = self.getOutputUri(uri, cur_sub)
            out_path = self.getOutputPath(sub_uri)

            # Check for up-to-date outputs.
            do_bake = True
            if not force_this:
                try:
                    in_path_time = record_entry.path_mtime
                    out_path_time = os.path.getmtime(out_path)
                    if out_path_time > in_path_time:
                        do_bake = False
                except OSError:
                    # File doesn't exist, we'll need to bake.
                    pass

            # If this page didn't bake because it's already up-to-date.
            # Keep trying for as many subs as we know this page has.
            if not do_bake:
                if (prev_record_entry is not None and
                        prev_record_entry.num_subs < cur_sub):
                    logger.debug("")
                    cur_sub += 1
                    has_more_subs = True
                    logger.debug("  %s is up to date, skipping to next "
                            "sub-page." % out_path)
                    continue

                # We don't know how many subs to expect... just skip.
                logger.debug("  %s is up to date, skipping bake." % out_path)
                break

            # All good, proceed.
            try:
                if invalidate_formatting:
                    cache_key = '%s:%s' % (uri, cur_sub)
                    self.app.env.rendered_segments_repository.invalidate(
                            cache_key)

                logger.debug("  p%d -> %s" % (cur_sub, out_path))
                ctx, rp = self._bakeSingle(page, sub_uri, cur_sub, out_path,
                        pagination_filter, custom_data)
            except Exception as ex:
                if self.app.debug:
                    logger.exception(ex)
                page_rel_path = os.path.relpath(page.path, self.app.root_dir)
                raise BakingError("%s: error baking '%s'." %
                        (page_rel_path, uri)) from ex

            # Copy page assets.
            if (cur_sub == 1 and self.copy_assets and
                    ctx.used_assets is not None):
                if self.pretty_urls:
                    out_assets_dir = os.path.dirname(out_path)
                else:
                    out_assets_dir, out_name = os.path.split(out_path)
                    if sub_uri != self.site_root:
                        out_name_noext, _ = os.path.splitext(out_name)
                        out_assets_dir += out_name_noext

                logger.debug("Copying page assets to: %s" % out_assets_dir)
                if not os.path.isdir(out_assets_dir):
                    os.makedirs(out_assets_dir, 0o755)
                for ap in ctx.used_assets:
                    dest_ap = os.path.join(out_assets_dir, os.path.basename(ap))
                    logger.debug("  %s -> %s" % (ap, dest_ap))
                    shutil.copy(ap, dest_ap)

            # Record what we did and figure out if we have more work.
            record_entry.out_uris.append(sub_uri)
            record_entry.out_paths.append(out_path)
            record_entry.used_source_names |= ctx.used_source_names
            record_entry.used_taxonomy_terms |= ctx.used_taxonomy_terms

            has_more_subs = False
            if (ctx.used_pagination is not None and
                    ctx.used_pagination.has_more):
                cur_sub += 1
                has_more_subs = True

    def _bakeSingle(self, page, sub_uri, num, out_path,
            pagination_filter=None, custom_data=None):
        ctx = PageRenderingContext(page, sub_uri)
        ctx.page_num = num
        if pagination_filter:
            ctx.pagination_filter = pagination_filter
        if custom_data:
            ctx.custom_data = custom_data

        rp = render_page(ctx)

        out_dir = os.path.dirname(out_path)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, 0o755)

        with codecs.open(out_path, 'w', 'utf8') as fp:
            fp.write(rp.content)

        return ctx, rp


class Baker(object):
    def __init__(self, app, out_dir, force=False, portable=False,
            no_assets=False, num_workers=4):
        assert app and out_dir
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.portable = portable
        self.no_assets = no_assets
        self.num_workers = num_workers

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
                'pages_' +
                hashlib.md5(self.out_dir.encode('utf8')).hexdigest() +
                '.record')
        if not self.force and record_cache.has(record_name):
            t = time.clock()
            record.loadPrevious(record_cache.getCachePath(record_name))
            logger.debug(format_timed(t, 'loaded previous bake record',
                colored=False));

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
        logger.debug(format_timed(start_time, 'done baking'));

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
            logger.info(format_timed(start_time,
                "cleaned cache (reason: %s)" % reason))
        else:
            record.incremental_count += 1
            logger.debug(format_timed(start_time, "cache is assumed valid",
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
                    logger.debug("Skipping taxonomy page: %s:%s" %
                            (source.name, fac.ref_spec))
                    continue

                entry = BakeRecordPageEntry(fac)
                record.addEntry(entry)

                route = self.app.getRoute(source.name, fac.metadata)
                if route is None:
                    entry.errors.append("Can't get route for page: %s" %
                            fac.ref_spec)
                    logger.error(entry.errors[-1])
                    continue

                queue.addJob(BakeWorkerJob(fac, route, entry))

        self._waitOnWorkerPool(pool, abort)

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
                    changed_terms = cur_entry.config.get(tax.name)
                elif (prev_entry and cur_entry and
                        cur_entry.was_baked_successfully):
                    changed_terms = []
                    prev_terms = prev_entry.config.get(tax.name)
                    cur_terms = cur_entry.config.get(tax.name)
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

                logger.debug("Baking '%s' for source '%s': %s" %
                        (tax_name, source_name, terms))
                tax = self.app.getTaxonomy(tax_name)
                route = self.app.getTaxonomyRoute(tax_name, source_name)
                tax_page_ref = tax.getPageRef(source_name)
                if not tax_page_ref.exists:
                    logger.debug("No taxonomy page found at '%s', skipping." %
                            tax.page_ref)
                    continue

                tax_page_source = tax_page_ref.source
                tax_page_rel_path = tax_page_ref.rel_path
                logger.debug("Using taxonomy page: %s:%s" %
                        (tax_page_source.name, tax_page_rel_path))

                for term in terms:
                    fac = PageFactory(tax_page_source, tax_page_rel_path,
                            {tax.term_name: term})
                    logger.debug("Queuing: %s [%s, %s]" %
                            (fac.ref_spec, tax_name, term))
                    entry = BakeRecordPageEntry(fac, tax_name, term)
                    record.addEntry(entry)
                    queue.addJob(
                            BakeWorkerJob(fac, route, entry, tax_name, term))

        self._waitOnWorkerPool(pool, abort)

    def _handleDeletetions(self, record):
        for path, reason in record.getDeletions():
            logger.debug("Removing '%s': %s" % (path, reason))
            os.remove(path)
            logger.info('[delete] %s' % path)

    def _createWorkerPool(self, record, pool_size=4):
        pool = []
        queue = BakeScheduler(record)
        abort = threading.Event()
        for i in range(pool_size):
            ctx = BakeWorkerContext(self.app, self.out_dir, self.force,
                    record, queue, abort)
            worker = BakeWorker(i, ctx)
            pool.append(worker)
        return pool, queue, abort

    def _waitOnWorkerPool(self, pool, abort):
        for w in pool:
            w.start()
        for w in pool:
            w.join()
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

            logger.debug("Job '%s:%s' is ready to go, moving to active "
                    "queue." % (job.factory.source.name, job.factory.rel_path))
            self._active_jobs.append(job)
            return job

    def _isJobReady(self, job):
        e = self.record.getPreviousEntry(job.factory.source.name,
                job.factory.rel_path)
        if not e:
            return (True, None)
        for sn, rp in e.used_source_names:
            if sn == job.factory.source.name:
                continue
            if any(filter(lambda j: j.factory.source.name == sn, self.jobs)):
                return (False, sn)
            if any(filter(lambda j: j.factory.source.name == sn,
                    self._active_jobs)):
                return (False, sn)
        return (True, None)


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
        self._page_baker = PageBaker(ctx.app, ctx.out_dir, ctx.force,
                ctx.record)

    def run(self):
        while(not self.ctx.abort_event.is_set()):
            try:
                job = self.ctx.work_queue.getNextJob(wait_timeout=1)
                if job is None:
                    logger.debug("[%d] No more work... shutting down." %
                            self.wid)
                    break

                self._unsafeRun(job)
                logger.debug("[%d] Done with page." % self.wid)
                self.ctx.work_queue.onJobFinished(job)
            except Exception as ex:
                self.ctx.abort_event.set()
                self.abort_exception = ex
                logger.debug("[%d] Critical error, aborting." % self.wid)
                if self.ctx.app.debug:
                    logger.exception(ex)
                break

    def _unsafeRun(self, job):
        start_time = time.clock()

        entry = job.record_entry
        try:
            self._page_baker.bake(job.factory, job.route, entry,
                    taxonomy_name=job.taxonomy_name,
                    taxonomy_term=job.taxonomy_term)
        except BakingError as ex:
            logger.debug("Got baking error. Adding it to the record.")
            while ex:
                entry.errors.append(str(ex))
                ex = ex.__cause__

        if entry.was_baked_successfully:
            uri = entry.out_uris[0]
            friendly_uri = uri if uri != '' else '[main page]'
            friendly_count = ''
            if entry.num_subs > 1:
                friendly_count = ' (%d pages)' % entry.num_subs
            logger.info(format_timed(start_time, '[%d] %s%s' %
                    (self.wid, friendly_uri, friendly_count)))
        elif entry.errors:
            for e in entry.errors:
                logger.error(e)

