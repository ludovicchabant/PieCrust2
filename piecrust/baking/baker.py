import time
import os.path
import codecs
import urllib.request, urllib.error, urllib.parse
import hashlib
import logging
import threading
from queue import Queue, Empty
from piecrust.baking.records import TransitionalBakeRecord, BakeRecordPageEntry
from piecrust.chefutil import format_timed
from piecrust.data.filters import (PaginationFilter, HasFilterClause,
        IsFilterClause, AndBooleanClause)
from piecrust.processing.base import ProcessorPipeline
from piecrust.rendering import PageRenderingContext, render_page
from piecrust.sources.base import (PageFactory,
        REALM_NAMES, REALM_USER, REALM_THEME)


logger = logging.getLogger(__name__)


class PageBaker(object):
    def __init__(self, app, out_dir, force=False, record=None,
            copy_assets=False):
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.record = record
        self.force = force
        self.copy_assets = copy_assets
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

        return os.path.join(*bake_path)

    def bake(self, factory, route, taxonomy_name=None, taxonomy_term=None):
        page = factory.buildPage()

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

        cur_sub = 1
        has_more_subs = True
        cur_record_entry = BakeRecordPageEntry(page)
        cur_record_entry.taxonomy_name = taxonomy_name
        cur_record_entry.taxonomy_term = taxonomy_term
        prev_record_entry = self.record.getPreviousEntry(page, taxonomy_name,
                taxonomy_term)

        logger.debug("Baking '%s'..." % uri)
        while has_more_subs:
            sub_uri = self.getOutputUri(uri, cur_sub)
            out_path = self.getOutputPath(sub_uri)

            # Check for up-to-date outputs.
            do_bake = True
            if not self.force and prev_record_entry:
                try:
                    in_path_time = os.path.getmtime(page.path)
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
                logger.debug("  p%d -> %s" % (cur_sub, out_path))
                ctx, rp = self._bakeSingle(page, sub_uri, cur_sub, out_path,
                        pagination_filter, custom_data)
            except Exception as ex:
                logger.exception("Error baking page '%s' for URI '%s': %s" %
                        (page.ref_spec, uri, ex))
                raise

            cur_record_entry.out_uris.append(sub_uri)
            cur_record_entry.out_paths.append(out_path)
            cur_record_entry.used_source_names |= ctx.used_source_names
            cur_record_entry.used_taxonomy_terms |= ctx.used_taxonomy_terms

            has_more_subs = False
            if ctx.used_pagination is not None:
                cur_record_entry.used_source_names.add(
                        ctx.used_pagination._source.name)
                if ctx.used_pagination.has_more:
                    cur_sub += 1
                    has_more_subs = True

        if self.record:
            self.record.addEntry(cur_record_entry)

        return cur_record_entry

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

        with codecs.open(out_path, 'w', 'utf-8') as fp:
            fp.write(rp.content)

        return ctx, rp


class Baker(object):
    def __init__(self, app, out_dir=None, force=False, portable=False,
            no_assets=False):
        self.app = app
        self.out_dir = out_dir or os.path.join(app.root_dir, '_counter')
        self.force = force
        self.portable = portable
        self.no_assets = no_assets
        self.num_workers = app.config.get('baker/workers') or 4

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
        self.app.env.base_asset_url_format = '%site_root%%uri%'

        # Make sure the output directory exists.
        if not os.path.isdir(self.out_dir):
            os.makedirs(self.out_dir, 0o755)

        # Load/create the bake record.
        record = TransitionalBakeRecord()
        record_cache = self.app.cache.getCache('bake_r')
        record_name = hashlib.md5(self.out_dir).hexdigest() + '.record'
        if not self.force and record_cache.has(record_name):
            t = time.clock()
            record.loadPrevious(record_cache.getCachePath(record_name))
            logger.debug(format_timed(t, 'loaded previous bake record',
                colored=False));

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

        # Bake the assets.
        if not self.no_assets:
            self._bakeAssets(record)

        # Save the bake record.
        t = time.clock()
        record.collapseRecords()
        record.saveCurrent(record_cache.getCachePath(record_name))
        logger.debug(format_timed(t, 'saved bake record', colored=False))

        # All done.
        self.app.config.set('baker/is_baking', False)
        logger.info('-------------------------');
        logger.info(format_timed(start_time, 'done baking'));

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

                route = self.app.getRoute(source.name, fac.metadata)
                if route is None:
                    logger.error("Can't get route for page: %s" % fac.ref_spec)
                    continue

                logger.debug("Queuing: %s" % fac.ref_spec)
                queue.put_nowait(BakeWorkerJob(fac, route))

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
                if not prev_entry and cur_entry and cur_entry.was_baked:
                    changed_terms = cur_entry.config.get(tax.name)
                elif prev_entry and cur_entry and cur_entry.was_baked:
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
                    queue.put_nowait(
                            BakeWorkerJob(fac, route, tax_name, term))

        self._waitOnWorkerPool(pool, abort)

    def _bakeAssets(self, record):
        baker_params = self.app.config.get('baker') or {}
        skip_patterns = baker_params.get('skip_patterns')
        force_patterns = baker_params.get('force_patterns')
        proc = ProcessorPipeline(
                self.app, self.out_dir, force=self.force,
                skip_patterns=skip_patterns, force_patterns=force_patterns,
                num_workers=self.num_workers)
        proc.run()

    def _createWorkerPool(self, record, pool_size=4):
        pool = []
        queue = Queue()
        abort = threading.Event()
        for i in range(pool_size):
            ctx = BakeWorkerContext(self.app, self.out_dir, self.force,
                    record, queue, abort)
            worker = BakeWorker(i, ctx)
            worker.start()
            pool.append(worker)
        return pool, queue, abort

    def _waitOnWorkerPool(self, pool, abort):
        for w in pool:
            w.join()
        if abort.is_set():
            raise Exception("Worker pool was aborted.")


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
    def __init__(self, factory, route, taxonomy_name=None, taxonomy_term=None):
        self.factory = factory
        self.route = route
        self.taxonomy_name = taxonomy_name
        self.taxonomy_term = taxonomy_term

    @property
    def source(self):
        return self.factory.source


class BakeWorker(threading.Thread):
    def __init__(self, wid, ctx):
        super(BakeWorker, self).__init__()
        self.wid = wid
        self.ctx = ctx
        self.num_bakes = 0
        self._page_baker = PageBaker(ctx.app, ctx.out_dir, ctx.force,
                ctx.record)

    def run(self):
        while(not self.ctx.abort_event.is_set()):
            try:
                job = self.ctx.work_queue.get(True, 0.1)
            except Empty:
                logger.debug("[%d] No more work... shutting down." % self.wid)
                break

            try:
                self._unsafeRun(job)
                logger.debug("[%d] Done with page." % self.wid)
                self.ctx.work_queue.task_done()
            except Exception as ex:
                self.ctx.abort_event.set()
                logger.error("[%d] Critical error, aborting." % self.wid)
                logger.exception(ex)
                break

    def _unsafeRun(self, job):
        start_time = time.clock()

        bake_res = self._page_baker.bake(job.factory, job.route,
                taxonomy_name=job.taxonomy_name,
                taxonomy_term=job.taxonomy_term)

        if bake_res.was_baked:
            uri = bake_res.out_uris[0]
            friendly_uri = uri if uri != '' else '[main page]'
            friendly_count = ''
            if bake_res.num_subs > 1:
                friendly_count = ' (%d pages)' % bake_res.num_subs
            logger.info(format_timed(start_time, '[%d] %s%s' %
                    (self.wid, friendly_uri, friendly_count)))
            self.num_bakes += 1

