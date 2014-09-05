import os
import os.path
import pickle
import logging
from piecrust.events import Event


logger = logging.getLogger(__name__)


class Record(object):
    def __init__(self):
        self.entries = []
        self.entry_added = Event()

    def addEntry(self, entry):
        self.entries.append(entry)
        self.entry_added.fire(entry)

    def save(self, path):
        path_dir = os.path.dirname(path)
        if not os.path.isdir(path_dir):
            os.makedirs(path_dir, 0o755)

        with open(path, 'wb') as fp:
            pickle.dump(self, fp, pickle.HIGHEST_PROTOCOL)

    def __getstate__(self):
        odict = self.__dict__.copy()
        del odict['entry_added']
        return odict

    def __setstate__(self, state):
        for k, v in state.items():
            setattr(self, k, v)
        self.entry_added = Event()

    @staticmethod
    def load(path):
        logger.debug("Loading bake record from: %s" % path)
        with open(path, 'rb') as fp:
            return pickle.load(fp)

