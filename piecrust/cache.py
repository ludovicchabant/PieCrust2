import os
import os.path
import shutil
import codecs
import logging
import threading


logger = logging.getLogger(__name__)


class ExtensibleCache(object):
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.lock = threading.Lock()
        self.caches = {}

    @property
    def enabled(self):
        return True

    def getCache(self, name):
        c = self.caches.get(name)
        if c is None:
            with self.lock:
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
        cache_path = self.getCachePath(path)
        logger.debug("Reading cache: %s" % cache_path)
        with codecs.open(cache_path, 'r', 'utf-8') as fp:
            return fp.read()

    def write(self, path, content):
        cache_path = self.getCachePath(path)
        cache_dir = os.path.dirname(cache_path)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir, 0o755)
        logger.debug("Writing cache: %s" % cache_path)
        with codecs.open(cache_path, 'w', 'utf-8') as fp:
            fp.write(content)

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

