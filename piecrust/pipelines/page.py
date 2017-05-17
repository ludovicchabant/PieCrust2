import hashlib
from piecrust.pipelines.base import ContentPipeline


class PagePipeline(ContentPipeline):
    PIPELINE_NAME = 'page'
    PIPELINE_PASSES = 3

    def initialize(self, ctx):
        pass

    def run(self, content_item, ctx):
        raise NotImplementedError()

    def shutdown(self, ctx):
        pass

    def collapseRecords(self, record_history):
        pass

    def getDeletions(self, record_history):
        for prev, cur in record_history.diffs():
            if prev and not cur:
                for sub in prev.subs:
                    yield (sub.out_path, 'previous source file was removed')
            elif prev and cur:
                prev_out_paths = [o.out_path for o in prev.subs]
                cur_out_paths = [o.out_path for o in cur.subs]
                diff = set(prev_out_paths) - set(cur_out_paths)
                for p in diff:
                    yield (p, 'source file changed outputs')


JOB_LOAD, JOB_RENDER_FIRST, JOB_BAKE = range(0, 3)


def _get_transition_key(path, extra_key=None):
    key = path
    if extra_key:
        key += '+%s' % extra_key
    return hashlib.md5(key.encode('utf8')).hexdigest()


# def getOverrideEntry(self, path, uri):
#     for pair in self.transitions.values():
#         cur = pair[1]
#         if cur and cur.path != path:
#             for o in cur.subs:
#                 if o.out_uri == uri:
#                     return cur
#     return None



#        # Create the job handlers.
#        job_handlers = {
#            JOB_LOAD: LoadJobHandler(self.ctx),
#            JOB_RENDER_FIRST: RenderFirstSubJobHandler(self.ctx),
#            JOB_BAKE: BakeJobHandler(self.ctx)}
#        for jt, jh in job_handlers.items():
#            app.env.registerTimer(type(jh).__name__)
#        self.job_handlers = job_handlers
#
#    def process(self, job):
#        handler = self.job_handlers[job['type']]
#        with self.ctx.app.env.timerScope(type(handler).__name__):
#            return handler.handleJob(job['job'])

#    def _loadRealmPages(self, record_history, pool, factories):
#        def _handler(res):
#            # Create the record entry for this page.
#            # This will also update the `dirty_source_names` for the record
#            # as we add page files whose last modification times are later
#            # than the last bake.
#            record_entry = BakeRecordEntry(res['source_name'], res['path'])
#            record_entry.config = res['config']
#            record_entry.timestamp = res['timestamp']
#            if res['errors']:
#                record_entry.errors += res['errors']
#                record_history.current.success = False
#                self._logErrors(res['path'], res['errors'])
#            record_history.addEntry(record_entry)
#
#        logger.debug("Loading %d realm pages..." % len(factories))
#        with format_timed_scope(logger,
#                                "loaded %d pages" % len(factories),
#                                level=logging.DEBUG, colored=False,
#                                timer_env=self.app.env,
#                                timer_category='LoadJob'):
#            jobs = []
#            for fac in factories:
#                job = {
#                        'type': JOB_LOAD,
#                        'job': save_factory(fac)}
#                jobs.append(job)
#            ar = pool.queueJobs(jobs, handler=_handler)
#            ar.wait()
#
#    def _renderRealmPages(self, record_history, pool, factories):
#        def _handler(res):
#            entry = record_history.getCurrentEntry(res['path'])
#            if res['errors']:
#                entry.errors += res['errors']
#                record_history.current.success = False
#                self._logErrors(res['path'], res['errors'])
#
#        logger.debug("Rendering %d realm pages..." % len(factories))
#        with format_timed_scope(logger,
#                                "prepared %d pages" % len(factories),
#                                level=logging.DEBUG, colored=False,
#                                timer_env=self.app.env,
#                                timer_category='RenderFirstSubJob'):
#            jobs = []
#            for fac in factories:
#                record_entry = record_history.getCurrentEntry(fac.path)
#                if record_entry.errors:
#                    logger.debug("Ignoring %s because it had previous "
#                                 "errors." % fac.ref_spec)
#                    continue
#
#                # Make sure the source and the route exist for this page,
#                # otherwise we add errors to the record entry and we'll skip
#                # this page for the rest of the bake.
#                source = self.app.getSource(fac.source.name)
#                if source is None:
#                    record_entry.errors.append(
#                            "Can't get source for page: %s" % fac.ref_spec)
#                    logger.error(record_entry.errors[-1])
#                    continue
#
#                route = self.app.getSourceRoute(fac.source.name, fac.metadata)
#                if route is None:
#                    record_entry.errors.append(
#                            "Can't get route for page: %s" % fac.ref_spec)
#                    logger.error(record_entry.errors[-1])
#                    continue
#
#                # All good, queue the job.
#                route_index = self.app.routes.index(route)
#                job = {
#                        'type': JOB_RENDER_FIRST,
#                        'job': {
#                            'factory_info': save_factory(fac),
#                            'route_index': route_index
#                            }
#                        }
#                jobs.append(job)
#
#            ar = pool.queueJobs(jobs, handler=_handler)
#            ar.wait()
#
#    def _bakeRealmPages(self, record_history, pool, realm, factories):
#        def _handler(res):
#            entry = record_history.getCurrentEntry(res['path'])
#            entry.subs = res['sub_entries']
#            if res['errors']:
#                entry.errors += res['errors']
#                self._logErrors(res['path'], res['errors'])
#            if entry.has_any_error:
#                record_history.current.success = False
#            if entry.subs and entry.was_any_sub_baked:
#                record_history.current.baked_count[realm] += 1
#                record_history.current.total_baked_count[realm] += len(entry.subs)
#
#        logger.debug("Baking %d realm pages..." % len(factories))
#        with format_timed_scope(logger,
#                                "baked %d pages" % len(factories),
#                                level=logging.DEBUG, colored=False,
#                                timer_env=self.app.env,
#                                timer_category='BakeJob'):
#            jobs = []
#            for fac in factories:
#                job = self._makeBakeJob(record_history, fac)
#                if job is not None:
#                    jobs.append(job)
#
#            ar = pool.queueJobs(jobs, handler=_handler)
#            ar.wait()
#


#    def _makeBakeJob(self, record_history, fac):
#        # Get the previous (if any) and current entry for this page.
#        pair = record_history.getPreviousAndCurrentEntries(fac.path)
#        assert pair is not None
#        prev_entry, cur_entry = pair
#        assert cur_entry is not None
#
#        # Ignore if there were errors in the previous passes.
#        if cur_entry.errors:
#            logger.debug("Ignoring %s because it had previous "
#                         "errors." % fac.ref_spec)
#            return None
#
#        # Build the route metadata and find the appropriate route.
#        page = fac.buildPage()
#        route_metadata = create_route_metadata(page)
#        route = self.app.getSourceRoute(fac.source.name, route_metadata)
#        assert route is not None
#
#        # Figure out if this page is overriden by another previously
#        # baked page. This happens for example when the user has
#        # made a page that has the same page/URL as a theme page.
#        uri = route.getUri(route_metadata)
#        override_entry = record_history.getOverrideEntry(page.path, uri)
#        if override_entry is not None:
#            override_source = self.app.getSource(
#                    override_entry.source_name)
#            if override_source.realm == fac.source.realm:
#                cur_entry.errors.append(
#                        "Page '%s' maps to URL '%s' but is overriden "
#                        "by page '%s'." %
#                        (fac.ref_spec, uri, override_entry.path))
#                logger.error(cur_entry.errors[-1])
#            cur_entry.flags |= BakeRecordEntry.FLAG_OVERRIDEN
#            return None
#
#        route_index = self.app.routes.index(route)
#        job = {
#                'type': JOB_BAKE,
#                'job': {
#                        'factory_info': save_factory(fac),
#                        'generator_name': None,
#                        'generator_record_key': None,
#                        'route_index': route_index,
#                        'route_metadata': route_metadata,
#                        'dirty_source_names': record_history.dirty_source_names
#                        }
#                }
#        return job
#
#    def _handleDeletetions(self, record_history):
#        logger.debug("Handling deletions...")
#        for path, reason in record_history.getDeletions():
#            logger.debug("Removing '%s': %s" % (path, reason))
#            record_history.current.deleted.append(path)
#            try:
#                os.remove(path)
#                logger.info('[delete] %s' % path)
#            except OSError:
#                # Not a big deal if that file had already been removed
#                # by the user.
#                pass
#



#def save_factory(fac):
#    return {
#        'source_name': fac.source.name,
#        'rel_path': fac.rel_path,
#        'metadata': fac.metadata}
#
#
#def load_factory(app, info):
#    source = app.getSource(info['source_name'])
#    return PageFactory(source, info['rel_path'], info['metadata'])
#
#
#class LoadJobHandler(JobHandler):
#    def handleJob(self, job):
#        # Just make sure the page has been cached.
#        fac = load_factory(self.app, job)
#        logger.debug("Loading page: %s" % fac.ref_spec)
#        self.app.env.addManifestEntry('LoadJobs', fac.ref_spec)
#        result = {
#            'source_name': fac.source.name,
#            'path': fac.path,
#            'config': None,
#            'timestamp': None,
#            'errors': None}
#        try:
#            page = fac.buildPage()
#            page._load()
#            result['config'] = page.config.getAll()
#            result['timestamp'] = page.datetime.timestamp()
#        except Exception as ex:
#            logger.debug("Got loading error. Sending it to master.")
#            result['errors'] = _get_errors(ex)
#            if self.ctx.app.debug:
#                logger.exception(ex)
#        return result
#
#
#class RenderFirstSubJobHandler(JobHandler):
#    def handleJob(self, job):
#        # Render the segments for the first sub-page of this page.
#        fac = load_factory(self.app, job['factory_info'])
#        self.app.env.addManifestEntry('RenderJobs', fac.ref_spec)
#
#        route_index = job['route_index']
#        route = self.app.routes[route_index]
#
#        page = fac.buildPage()
#        qp = QualifiedPage(page, route, route_metadata)
#        ctx = RenderingContext(qp)
#        self.app.env.abort_source_use = True
#
#        result = {
#            'path': fac.path,
#            'aborted': False,
#            'errors': None}
#        logger.debug("Preparing page: %s" % fac.ref_spec)
#        try:
#            render_page_segments(ctx)
#        except AbortedSourceUseError:
#            logger.debug("Page %s was aborted." % fac.ref_spec)
#            self.app.env.stepCounter("SourceUseAbortions")
#            result['aborted'] = True
#        except Exception as ex:
#            logger.debug("Got rendering error. Sending it to master.")
#            result['errors'] = _get_errors(ex)
#            if self.ctx.app.debug:
#                logger.exception(ex)
#        finally:
#            self.app.env.abort_source_use = False
#        return result
#
#
#class BakeJobHandler(JobHandler):
#    def __init__(self, ctx):
#        super(BakeJobHandler, self).__init__(ctx)
#        self.page_baker = PageBaker(ctx.app, ctx.out_dir, ctx.force)
#
#    def shutdown(self):
#        self.page_baker.shutdown()
#
#    def handleJob(self, job):
#        # Actually bake the page and all its sub-pages to the output folder.
#        fac = load_factory(self.app, job['factory_info'])
#        self.app.env.addManifestEntry('BakeJobs', fac.ref_spec)
#
#        route_index = job['route_index']
#        route_metadata = job['route_metadata']
#        route = self.app.routes[route_index]
#
#        gen_name = job['generator_name']
#        gen_key = job['generator_record_key']
#        dirty_source_names = job['dirty_source_names']
#
#        page = fac.buildPage()
#        qp = QualifiedPage(page, route, route_metadata)
#
#        result = {
#            'path': fac.path,
#            'generator_name': gen_name,
#            'generator_record_key': gen_key,
#            'sub_entries': None,
#            'errors': None}
#
#        if job.get('needs_config', False):
#            result['config'] = page.config.getAll()
#
#        previous_entry = None
#        if self.ctx.previous_record_index is not None:
#            key = _get_transition_key(fac.path, gen_key)
#            previous_entry = self.ctx.previous_record_index.get(key)
#
#        logger.debug("Baking page: %s" % fac.ref_spec)
#        logger.debug("With route metadata: %s" % route_metadata)
#        try:
#            sub_entries = self.page_baker.bake(
#                qp, previous_entry, dirty_source_names, gen_name)
#            result['sub_entries'] = sub_entries
#
#        except Exception as ex:
#            logger.debug("Got baking error. Sending it to master.")
#            result['errors'] = _get_errors(ex)
#            if self.ctx.app.debug:
#                logger.exception(ex)
#
#        return result
#
