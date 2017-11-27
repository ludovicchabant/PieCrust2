import os
import os.path
import shutil
import pickle
import hashlib
import logging
import repoze.lru


logger = logging.getLogger(__name__)


class ExtensibleCache(object):
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.caches = {}

    @property
    def enabled(self):
        return True

    def getCache(self, name):
        c = self.caches.get(name)
        if c is None:
            c_dir = os.path.join(self.base_dir, name)
            if not os.path.isdir(c_dir):
                os.makedirs(c_dir, 0o755)

            c = SimpleCache(c_dir)
            self.caches[name] = c
        return c

    def getCacheDir(self, name):
        return os.path.join(self.base_dir, name)

    def getCacheNames(self, except_names=None):
        _, dirnames, __ = next(os.walk(self.base_dir))
        if except_names is None:
            return dirnames
        return [dn for dn in dirnames if dn not in except_names]

    def clearCache(self, name):
        cache_dir = self.getCacheDir(name)
        if os.path.isdir(cache_dir):
            logger.debug("Cleaning cache: %s" % cache_dir)
            shutil.rmtree(cache_dir)

            # Re-create the cache-dir because now our Cache instance points
            # to a directory that doesn't exist anymore.
            os.makedirs(cache_dir, 0o755)

    def clearCaches(self, except_names=None):
        for name in self.getCacheNames(except_names=except_names):
            self.clearCache(name)


class SimpleCache(object):
    def __init__(self, base_dir):
        self.base_dir = base_dir
        if not os.path.isdir(base_dir):
            raise Exception("Cache directory doesn't exist: %s" % base_dir)

    def isValid(self, path, time):
        cache_time = self.getCacheTime(path)
        if cache_time is None:
            return False
        if isinstance(time, list):
            for t in time:
                if cache_time < t:
                    return False
            return True
        return cache_time >= time

    def getCacheTime(self, path):
        cache_path = self.getCachePath(path)
        try:
            return os.path.getmtime(cache_path)
        except os.error:
            return None

    def has(self, path):
        cache_path = self.getCachePath(path)
        return os.path.isfile(cache_path)

    def read(self, path):
        with self.openRead(path, mode='r', encoding='utf8') as fp:
            return fp.read()

    def openRead(self, path, mode='r', encoding=None):
        cache_path = self.getCachePath(path)
        return open(cache_path, mode=mode, encoding=encoding)

    def write(self, path, content):
        with self.openWrite(path, mode='w', encoding='utf8') as fp:
            fp.write(content)

    def openWrite(self, path, mode='w', encoding=None):
        cache_path = self.getCachePath(path)
        cache_dir = os.path.dirname(cache_path)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir, 0o755)
        return open(cache_path, mode=mode, encoding=encoding)

    def getCachePath(self, path):
        if path.startswith('.'):
            path = '__index__' + path
        return os.path.join(self.base_dir, path)


class NullCache(object):
    def isValid(self, path, time):
        return False

    def getCacheTime(self, path):
        return None

    def has(self, path):
        return False

    def read(self, path):
        raise Exception("Null cache has no data.")

    def write(self, path, content):
        pass

    def getCachePath(self, path):
        raise Exception("Null cache can't make paths.")


class NullExtensibleCache(object):
    def __init__(self):
        self.null_cache = NullCache()

    @property
    def enabled(self):
        return False

    def getCache(self, name):
        return self.null_cache

    def getCacheDir(self, name):
        raise NotImplementedError()

    def getCacheNames(self, except_names=None):
        return []

    def clearCache(self, name):
        pass

    def clearCaches(self, except_names=None):
        pass


def _make_fs_cache_key(key):
    return hashlib.md5(key.encode('utf8')).hexdigest()


class MemCache(object):
    """ Simple memory cache. It can be backed by a simple file-system
        cache, but items need to be pickle-able to do this.
    """
    def __init__(self, size=2048):
        self.cache = repoze.lru.LRUCache(size)
        self.fs_cache = None
        self._last_access_hit = None
        self._invalidated_fs_items = set()
        self._missed_keys = []
        self._misses = 0
        self._hits = 0

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
            with self.fs_cache.openWrite(fs_key, mode='wb') as fp:
                pickle.dump(item, fp, pickle.HIGHEST_PROTOCOL)

    def get(self, key, item_maker, fs_cache_time=None, save_to_fs=True):
        self._last_access_hit = True
        item = self.cache.get(key)
        if item is not None:
            self._hits += 1
            return item

        if self.fs_cache is not None:
            if fs_cache_time is None:
                raise ValueError(
                    "No file-system cache time was given for '%s'. "
                    "This would result in degraded performance." % key)

            # Try first from the file-system cache.
            fs_key = _make_fs_cache_key(key)
            if (fs_key not in self._invalidated_fs_items and
                    self.fs_cache.isValid(fs_key, fs_cache_time)):
                with self.fs_cache.openRead(fs_key, mode='rb') as fp:
                    item = pickle.load(fp)
                self.cache.put(key, item)
                self._hits += 1
                return item

        # Look into the mem-cache.
        item = item_maker()
        self.cache.put(key, item)
        self._last_access_hit = False
        self._misses += 1
        self._missed_keys.append(key)

        # Save to the file-system if needed.
        if self.fs_cache is not None and save_to_fs:
            with self.fs_cache.openWrite(fs_key, mode='wb') as fp:
                pickle.dump(item, fp, pickle.HIGHEST_PROTOCOL)

        return item

