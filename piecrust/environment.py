import time
import logging
import contextlib
from piecrust.cache import MemCache


logger = logging.getLogger(__name__)


class AbortedSourceUseError(Exception):
    pass


class ExecutionInfo(object):
    def __init__(self, page, render_ctx):
        self.page = page
        self.render_ctx = render_ctx
        self.was_cache_valid = False
        self.start_time = time.perf_counter()


class ExecutionInfoStack(object):
    def __init__(self):
        self._page_stack = []

    @property
    def current_page_info(self):
        if len(self._page_stack) == 0:
            return None
        return self._page_stack[-1]

    @property
    def is_main_page(self):
        return len(self._page_stack) == 1

    def hasPage(self, page):
        for ei in self._page_stack:
            if ei.page == page:
                return True
        return False

    def pushPage(self, page, render_ctx):
        if len(self._page_stack) > 0:
            top = self._page_stack[-1]
            assert top.page is not page
        self._page_stack.append(ExecutionInfo(page, render_ctx))

    def popPage(self):
        del self._page_stack[-1]

    def clear(self):
        self._page_stack = []


class ExecutionStats(object):
    def __init__(self):
        self.timers = {}
        self.counters = {}
        self.manifests = {}

    def registerTimer(self, category, *, raise_if_registered=True):
        if raise_if_registered and category in self.timers:
            raise Exception("Timer '%s' has already been registered." %
                            category)
        self.timers[category] = 0

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


class Environment(object):
    def __init__(self):
        self.app = None
        self.start_time = None
        self.exec_info_stack = ExecutionInfoStack()
        self.was_cache_cleaned = False
        self.base_asset_url_format = '%uri%'
        self.page_repository = MemCache()
        self.rendered_segments_repository = MemCache()
        self.fs_caches = {
                'renders': self.rendered_segments_repository}
        self.fs_cache_only_for_main_page = False
        self.abort_source_use = False
        self._default_layout_extensions = None
        self._stats = ExecutionStats()

    @property
    def default_layout_extensions(self):
        if self._default_layout_extensions is not None:
            return self._default_layout_extensions

        if self.app is None:
            raise Exception("This environment has not been initialized yet.")

        from piecrust.rendering import get_template_engine
        dte = get_template_engine(self.app, None)
        self._default_layout_extensions = ['.' + e.lstrip('.')
                                           for e in dte.EXTENSIONS]
        return self._default_layout_extensions

    def initialize(self, app):
        self.app = app
        self.start_time = time.perf_counter()
        self.exec_info_stack.clear()
        self.was_cache_cleaned = False
        self.base_asset_url_format = '%uri%'

        for name, repo in self.fs_caches.items():
            cache = app.cache.getCache(name)
            repo.fs_cache = cache

    def registerTimer(self, category, *, raise_if_registered=True):
        self._stats.registerTimer(
                category, raise_if_registered=raise_if_registered)

    def timerScope(self, category):
        return self._stats.timerScope(category)

    def stepTimer(self, category, value):
        self._stats.stepTimer(category, value)

    def stepTimerSince(self, category, since):
        self._stats.stepTimerSince(category, since)

    def registerCounter(self, category, *, raise_if_registered=True):
        self._stats.registerCounter(
                category, raise_if_registered=raise_if_registered)

    def stepCounter(self, category, inc=1):
        self._stats.stepCounter(category, inc)

    def registerManifest(self, name, *, raise_if_registered=True):
        self._stats.registerManifest(
                name, raise_if_registered=raise_if_registered)

    def addManifestEntry(self, name, entry):
        self._stats.addManifestEntry(name, entry)

    def getStats(self):
        repos = [
                ('RenderedSegmentsRepo', self.rendered_segments_repository),
                ('PagesRepo', self.page_repository)]
        for name, repo in repos:
            self._stats.counters['%s_hit' % name] = repo._hits
            self._stats.counters['%s_miss' % name] = repo._misses
            self._stats.manifests['%s_missedKeys' % name] = list(repo._missed_keys)
        return self._stats


class StandardEnvironment(Environment):
    def __init__(self):
        super(StandardEnvironment, self).__init__()

