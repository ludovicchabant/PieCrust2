import os.path
import time
import logging
import yaml
from piecrust.processing.base import Processor


logger = logging.getLogger(__name__)


class _ConcatInfo(object):
    timestamp = 0
    files = None
    delim = "\n"


class ConcatProcessor(Processor):
    PROCESSOR_NAME = 'concat'

    def __init__(self):
        super(ConcatProcessor, self).__init__()
        self._cache = {}

    def matches(self, path):
        return path.endswith('.concat')

    def getDependencies(self, path):
        info = self._load(path)
        return info.files

    def getOutputFilenames(self, filename):
        return [filename[:-7]]

    def process(self, path, out_dir):
        dirname, filename = os.path.split(path)
        out_path = os.path.join(out_dir, filename[:-7])
        info = self._load(path)
        if not info.files:
            raise Exception("No files specified in: %s" %
                            os.path.relpath(path, self.app.root_dir))

        logger.debug("Concatenating %d files to: %s" %
                     (len(info.files), out_path))
        encoded_delim = info.delim.encode('utf8')
        with open(out_path, 'wb') as ofp:
            for p in info.files:
                with open(p, 'rb') as ifp:
                    ofp.write(ifp.read())
                if info.delim:
                    ofp.write(encoded_delim)
        return True

    def _load(self, path):
        cur_time = time.time()
        info = self._cache.get(path)
        if (info is not None and
                (cur_time - info.timestamp <= 1 or
                 os.path.getmtime(path) < info.timestamp)):
            return info

        if info is None:
            info = _ConcatInfo()
            self._cache[path] = info

        with open(path, 'r') as fp:
            config = yaml.load(fp)

        info.files = config.get('files', [])
        info.delim = config.get('delim', "\n")
        info.timestamp = cur_time

        path_mode = config.get('path_mode', 'relative')
        if path_mode == 'relative':
            dirname, _ = os.path.split(path)
            info.files = [os.path.join(dirname, f) for f in info.files]
        elif path_mode == 'absolute':
            info.files = [self.app.resolvePath(f) for f in info.files]
        else:
            raise Exception("Unknown path mode: %s" % path_mode)

        return info

