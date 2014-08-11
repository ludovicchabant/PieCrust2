import os
import os.path
import logging
from piecrust import APP_VERSION
from piecrust.events import Event

try:
    import cPickle as pickle
except ImportError:
    import pickle


logger = logging.getLogger(__name__)


class Record(object):
    VERSION = 1

    def __init__(self):
        self.app_version = None
        self.record_version = None
        self.entries = []
        self.entry_added = Event()

    def isVersionMatch(self):
        return (self.app_version == APP_VERSION and
                self.record_version == self.VERSION)

    def addEntry(self, entry):
        self.entries.append(entry)
        self.entry_added.fire(entry)

    def save(self, path):
        path_dir = os.path.dirname(path)
        if not os.path.isdir(path_dir):
            os.makedirs(path_dir, 0755)

        with open(path, 'w') as fp:
            pickle.dump(self, fp, pickle.HIGHEST_PROTOCOL)

    def __getstate__(self):
        odict = self.__dict__.copy()
        del odict['entry_added']
        return odict

    @staticmethod
    def load(path):
        logger.debug("Loading bake record from: %s" % path)
        with open(path, 'r') as fp:
            return pickle.load(fp)

