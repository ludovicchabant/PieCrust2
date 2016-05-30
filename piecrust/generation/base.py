from werkzeug.utils import cached_property
from piecrust.baking.records import BakeRecordEntry
from piecrust.baking.worker import save_factory, JOB_BAKE
from piecrust.configuration import ConfigurationError
from piecrust.routing import create_route_metadata
from piecrust.sources.pageref import PageRef


class InvalidRecordExtraKey(Exception):
    pass


class PageGeneratorBakeContext(object):
    def __init__(self, app, record, pool, generator):
        self._app = app
        self._record = record
        self._pool = pool
        self._generator = generator
        self._job_queue = []
        self._is_running = False

    def getRecordExtraKey(self, seed):
        return '%s:%s' % (self._generator.name, seed)

    def matchesRecordExtraKey(self, extra_key):
        return (extra_key is not None and
                extra_key.startswith(self._generator.name + ':'))

    def getSeedFromRecordExtraKey(self, extra_key):
        if not self.matchesRecordExtraKey(extra_key):
            raise InvalidRecordExtraKey("Invalid extra key: %s" % extra_key)
        return extra_key[len(self._generator.name) + 1:]

    def getAllPageRecords(self):
        return self._record.transitions.values()

    def getBakedPageRecords(self):
        for prev, cur in self.getAllPageRecords():
            if cur and cur.was_any_sub_baked:
                yield (prev, cur)

    def collapseRecord(self, entry):
        self._record.collapseEntry(entry)

    def queueBakeJob(self, page_fac, route, extra_route_metadata, seed):
        if self._is_running:
            raise Exception("The job queue is running.")

        extra_key = self.getRecordExtraKey(seed)
        entry = BakeRecordEntry(
                page_fac.source.name,
                page_fac.path,
                extra_key)
        self._record.addEntry(entry)

        page = page_fac.buildPage()
        route_metadata = create_route_metadata(page)
        route_metadata.update(extra_route_metadata)
        uri = route.getUri(route_metadata)
        override_entry = self._record.getOverrideEntry(page.path, uri)
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
            return

        route_index = self._app.routes.index(route)
        job = {
                'type': JOB_BAKE,
                'job': {
                        'factory_info': save_factory(page_fac),
                        'generator_name': self._generator.name,
                        'generator_record_key': extra_key,
                        'route_index': route_index,
                        'route_metadata': route_metadata,
                        'dirty_source_names': self._record.dirty_source_names,
                        'needs_config': True
                        }
                }
        self._job_queue.append(job)

    def runJobQueue(self):
        def _handler(res):
            entry = self._record.getCurrentEntry(
                    res['path'], res['generator_record_key'])
            entry.config = res['config']
            entry.subs = res['sub_entries']
            if res['errors']:
                entry.errors += res['errors']
            if entry.has_any_error:
                self._record.current.success = False

        self._is_running = True
        try:
            ar = self._pool.queueJobs(self._job_queue, handler=_handler)
            ar.wait()
        finally:
            self._is_running = False


class PageGenerator(object):
    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config or {}

        self.source_name = config.get('source')
        if self.source_name is None:
            raise ConfigurationError(
                    "Generator '%s' requires a source name" % name)

        page_ref = config.get('page')
        if page_ref is None:
            raise ConfigurationError(
                    "Generator '%s' requires a listing page ref." % name)
        self.page_ref = PageRef(app, page_ref)

    @cached_property
    def source(self):
        for src in self.app.sources:
            if src.name == self.source_name:
                return src
        raise Exception("Can't find source '%s' for generator '%s'." % (
            self.source_name, self.name))

    def getPageFactory(self, route_metadata):
        # This will raise `PageNotFoundError` naturally if not found.
        return self.page_ref.getFactory()

    def bake(self, ctx):
        raise NotImplementedError()

    def onRouteFunctionUsed(self, route, route_metadata):
        pass

