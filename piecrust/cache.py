import os
import os.path
import codecs


class SimpleCache(object):
    def __init__(self, base_dir):
        if not os.path.isdir(base_dir):
            os.makedirs(base_dir, 0755)
        self.base_dir = base_dir

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
        with codecs.open(cache_path, 'r', 'utf-8') as fp:
            return fp.read()

    def write(self, path, content):
        cache_path = self.getCachePath(path)
        cache_dir = os.path.dirname(cache_path)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir, 0755)
        with codecs.open(cache_path, 'w', 'utf-8') as fp:
            fp.write(content)

