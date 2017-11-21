import time
import logging
import contextlib


logger = logging.getLogger(__name__)


class ExecutionStats:
    def __init__(self):
        self.timers = {}
        self.counters = {}
        self.manifests = {}

    def registerTimer(self, category, *,
                      raise_if_registered=True, time=0):
        if raise_if_registered and category in self.timers:
            raise Exception("Timer '%s' has already been registered." %
                            category)
        self.timers[category] = time

    @contextlib.contextmanager
    def timerScope(self, category):
        start = time.perf_counter()
        yield
        self.timers[category] += time.perf_counter() - start

    def stepTimer(self, category, value):
        self.timers[category] += value

    def stepTimerSince(self, category, since):
        self.stepTimer(category, time.perf_counter() - since)

    def registerCounter(self, category, *, raise_if_registered=True):
        if raise_if_registered and category in self.counters:
            raise Exception("Counter '%s' has already been registered." %
                            category)
        self.counters[category] = 0

    def stepCounter(self, category, inc=1):
        self.counters[category] += inc

    def registerManifest(self, name, *, raise_if_registered=True):
        if raise_if_registered and name in self.manifests:
            raise Exception("Manifest '%s' has already been registered." %
                            name)
        self.manifests[name] = []

    def addManifestEntry(self, name, entry):
        self.manifests[name].append(entry)

    def mergeStats(self, other):
        for oc, ov in other.timers.items():
            v = self.timers.setdefault(oc, 0)
            self.timers[oc] = v + ov
        for oc, ov in other.counters.items():
            v = self.counters.setdefault(oc, 0)
            self.counters[oc] = v + ov
        for oc, ov in other.manifests.items():
            v = self.manifests.setdefault(oc, [])
            self.manifests[oc] = v + ov

    def toData(self):
        return {
            'timers': self.timers.copy(),
            'counters': self.counters.copy(),
            'manifests': self.manifests.copy()}

    def fromData(self, data):
        self.timers = data['timers']
        self.counters = data['counters']
        self.manifests = data['manifests']


class Environment:
    def __init__(self):
        from piecrust.cache import MemCache
        from piecrust.rendering import RenderingContextStack

        self.app = None
        self.start_time = None
        self.was_cache_cleaned = False
        self.page_repository = MemCache()
        self.rendered_segments_repository = MemCache()
        self.render_ctx_stack = RenderingContextStack()
        self.fs_cache_only_for_main_page = False
        self.abort_source_use = False
        self._stats = ExecutionStats()

    @property
    def stats(self):
        return self._stats

    def initialize(self, app):
        self.app = app
        self.start_time = time.perf_counter()

        self.rendered_segments_repository.fs_cache = \
            app.cache.getCache('renders')

    def _mergeCacheStats(self):
        repos = [
            ('RenderedSegmentsRepo', self.rendered_segments_repository),
            ('PagesRepo', self.page_repository)]
        for name, repo in repos:
            self._stats.counters['%s_hit' % name] = repo._hits
            self._stats.counters['%s_miss' % name] = repo._misses
            self._stats.manifests['%s_missedKeys' % name] = \
                list(repo._missed_keys)


class StandardEnvironment(Environment):
    def __init__(self):
        super(StandardEnvironment, self).__init__()

