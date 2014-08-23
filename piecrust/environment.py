import re
import time
import json
import logging
import threading
import repoze.lru


logger = logging.getLogger(__name__)


re_fs_cache_key = re.compile(r'[^\d\w\-\._]+')


def _make_fs_cache_key(key):
    return re_fs_cache_key.sub('_', key)


class MemCache(object):
    """ Simple memory cache. It can be backed by a simple file-system
        cache, but items need to be JSON-serializable to do this.
    """
    def __init__(self, size=2048):
        self.cache = repoze.lru.LRUCache(size)
        self.lock = threading.RLock()
        self.fs_cache = None

    def get(self, key, item_maker, fs_cache_time=None):
        item = self.cache.get(key)
        if item is None:
            logger.debug("Acquiring lock for: %s" % key)
            with self.lock:
                item = self.cache.get(key)
                if item is None:
                    if (self.fs_cache is not None and
                            fs_cache_time is not None):
                        # Try first from the file-system cache.
                        fs_key = _make_fs_cache_key(key)
                        if self.fs_cache.isValid(fs_key, fs_cache_time):
                            logger.debug("'%s' found in file-system cache." %
                                         key)
                            item_raw = self.fs_cache.read(fs_key)
                            item = json.loads(item_raw)
                            self.cache.put(key, item)
                            return item

                    # Look into the mem-cache.
                    logger.debug("'%s' not found in cache, must build." % key)
                    item = item_maker()
                    self.cache.put(key, item)

                    # Save to the file-system if needed.
                    if (self.fs_cache is not None and
                            fs_cache_time is not None):
                        item_raw = json.dumps(item)
                        self.fs_cache.write(fs_key, item_raw)
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
        self.base_asset_url_format = '%uri%'

    def initialize(self, app):
        cache = app.cache.getCache('renders')
        self.rendered_segments_repository.fs_cache = cache


class StandardEnvironment(Environment):
    def __init__(self):
        super(StandardEnvironment, self).__init__()

