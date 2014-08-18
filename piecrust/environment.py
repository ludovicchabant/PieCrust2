import time
import logging
import threading
import repoze.lru


logger = logging.getLogger(__name__)


class MemCache(object):
    def __init__(self, size=2048):
        self.cache = repoze.lru.LRUCache(size)
        self.lock = threading.RLock()

    def get(self, key, item_maker):
        item = self.cache.get(key)
        if item is None:
            logger.debug("Acquiring lock for: %s" % key)
            with self.lock:
                item = self.cache.get(key)
                if item is None:
                    logger.debug("'%s' not found in cache, must build." % key)
                    item = item_maker()
                    self.cache.put(key, item)
        return item


PHASE_PAGE_PARSING = 0
PHASE_PAGE_FORMATTING = 1
PHASE_PAGE_RENDERING = 2


class ExecutionInfo(object):
    def __init__(self, page, phase, render_ctx):
        self.page = page
        self.phase = phase
        self.render_ctx = render_ctx
        self.was_cache_valid = False
        self.start_time = time.clock()


class ExecutionInfoStack(threading.local):
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

    def pushPage(self, page, phase, render_ctx):
        self._page_stack.append(ExecutionInfo(page, phase, render_ctx))

    def popPage(self):
        del self._page_stack[-1]


class Environment(object):
    def __init__(self):
        self.start_time = time.clock()
        self.exec_info_stack = ExecutionInfoStack()
        self.was_cache_cleaned = False
        self.page_repository = MemCache()
        self.rendered_segments_repository = MemCache()
        self.base_asset_url_format = '%site_root%%uri%'

    def initialize(self, app):
        pass


class StandardEnvironment(Environment):
    def __init__(self):
        super(StandardEnvironment, self).__init__()

