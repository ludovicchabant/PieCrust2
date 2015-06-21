import time
import json
import logging
import hashlib
import contextlib
import collections
import repoze.lru


logger = logging.getLogger(__name__)


def _make_fs_cache_key(key):
    return hashlib.md5(key.encode('utf8')).hexdigest()


class MemCache(object):
    """ Simple memory cache. It can be backed by a simple file-system
        cache, but items need to be JSON-serializable to do this.
    """
    def __init__(self, size=2048):
        self.cache = repoze.lru.LRUCache(size)
        self.fs_cache = None
        self._last_access_hit = None
        self._invalidated_fs_items = set()

    @property
    def last_access_hit(self):
        return self._last_access_hit

    def invalidate(self, key):
        logger.debug("Invalidating cache item '%s'." % key)
        self.cache.invalidate(key)
        if self.fs_cache:
            logger.debug("Invalidating FS cache item '%s'." % key)
            fs_key = _make_fs_cache_key(key)
            self._invalidated_fs_items.add(fs_key)

    def put(self, key, item, save_to_fs=True):
        self.cache.put(key, item)
        if self.fs_cache and save_to_fs:
            fs_key = _make_fs_cache_key(key)
            item_raw = json.dumps(item)
            self.fs_cache.write(fs_key, item_raw)

    def get(self, key, item_maker, fs_cache_time=None, save_to_fs=True):
        self._last_access_hit = True
        item = self.cache.get(key)
        if item is None:
            if (self.fs_cache is not None and
                    fs_cache_time is not None):
                # Try first from the file-system cache.
                fs_key = _make_fs_cache_key(key)
                if (fs_key not in self._invalidated_fs_items and
                        self.fs_cache.isValid(fs_key, fs_cache_time)):
                    logger.debug("'%s' found in file-system cache." %
                                 key)
                    item_raw = self.fs_cache.read(fs_key)
                    item = json.loads(
                            item_raw,
                            object_pairs_hook=collections.OrderedDict)
                    self.cache.put(key, item)
                    return item

            # Look into the mem-cache.
            logger.debug("'%s' not found in cache, must build." % key)
            item = item_maker()
            self.cache.put(key, item)
            self._last_access_hit = False

            # Save to the file-system if needed.
            if self.fs_cache is not None and save_to_fs:
                item_raw = json.dumps(item)
                self.fs_cache.write(fs_key, item_raw)

        return item


class ExecutionInfo(object):
    def __init__(self, page, render_ctx):
        self.page = page
        self.render_ctx = render_ctx
        self.was_cache_valid = False
        self.start_time = time.clock()


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


class Environment(object):
    def __init__(self):
        self.start_time = None
        self.exec_info_stack = ExecutionInfoStack()
        self.was_cache_cleaned = False
        self.base_asset_url_format = '%uri%'
        self.page_repository = MemCache()
        self.rendered_segments_repository = MemCache()
        self.fs_caches = {
                'renders': self.rendered_segments_repository}
        self.fs_cache_only_for_main_page = False
        self._timers = {}

    def initialize(self, app):
        self.start_time = time.perf_counter()
        self.exec_info_stack.clear()
        self.was_cache_cleaned = False
        self.base_asset_url_format = '%uri%'
        self._onSubCacheDirChanged(app)

    def registerTimer(self, category, *, raise_if_registered=True):
        if raise_if_registered and category in self._timers:
            raise Exception("Timer '%s' has already been registered." %
                            category)
        self._timers[category] = 0

    @contextlib.contextmanager
    def timerScope(self, category):
        start = time.perf_counter()
        yield
        self._timers[category] += time.perf_counter() - start

    def stepTimer(self, category, value):
        self._timers[category] += value

    def _onSubCacheDirChanged(self, app):
        for name, repo in self.fs_caches.items():
            cache = app.cache.getCache(name)
            repo.fs_cache = cache


class StandardEnvironment(Environment):
    def __init__(self):
        super(StandardEnvironment, self).__init__()

