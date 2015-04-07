import os
import os.path
import pickle
import logging
from piecrust import APP_VERSION
from piecrust.events import Event


logger = logging.getLogger(__name__)


class Record(object):
    def __init__(self):
        self.entries = []
        self.entry_added = Event()
        self.app_version = APP_VERSION
        self.record_version = self.__class__.RECORD_VERSION

    def hasLatestVersion(self):
        return (self.app_version == APP_VERSION and
                self.record_version == self.__class__.RECORD_VERSION)

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
        state['entry_added'] = Event()
        self.__dict__.update(state)

    @staticmethod
    def load(path):
        logger.debug("Loading bake record from: %s" % path)
        with open(path, 'rb') as fp:
            return pickle.load(fp)


class TransitionalRecord(object):
    def __init__(self, record_class, previous_path=None):
        self._record_class = record_class
        self.transitions = {}
        self.incremental_count = 0
        self.current = record_class()
        if previous_path:
            self.loadPrevious(previous_path)
        else:
            self.previous = record_class()
        self.current.entry_added += self._onCurrentEntryAdded

    def loadPrevious(self, previous_path):
        previous_record_valid = True
        try:
            self.previous = self._record_class.load(previous_path)
        except Exception as ex:
            logger.debug("Error loading previous record: %s" % ex)
            logger.debug("Will reset to an empty one.")
            previous_record_valid = False

        if self.previous.record_version != self._record_class.RECORD_VERSION:
            logger.debug(
                    "Previous record has old version %s." %
                    self.previous.record_version)
            logger.debug("Will reset to an empty one.")
            previous_record_valid = False

        if not previous_record_valid:
            self.previous = self._record_class()
            return

        self._rebuildTransitions()

    def setPrevious(self, previous_record):
        self.previous = previous_record
        self._rebuildTransitions()

    def clearPrevious(self):
        self.setPrevious(self._record_class())

    def saveCurrent(self, current_path):
        self.current.save(current_path)

    def detach(self):
        res = self.current
        self.current.entry_added -= self._onCurrentEntryAdded
        self.current = None
        self.previous = None
        self.transitions = {}
        return res

    def addEntry(self, entry):
        self.current.addEntry(entry)

    def getTransitionKey(self, entry):
        raise NotImplementedError()

    def _rebuildTransitions(self):
        self.transitions = {}
        for e in self.previous.entries:
            key = self.getTransitionKey(e)
            self.transitions[key] = (e, None)

    def _onCurrentEntryAdded(self, entry):
        key = self.getTransitionKey(entry)
        te = self.transitions.get(key)
        if te is None:
            logger.debug("Adding new record entry: %s" % key)
            self.transitions[key] = (None, entry)
            self._onNewEntryAdded(entry)
            return

        if te[1] is not None:
            raise Exception("A current entry already exists for: %s" %
                    key)
        logger.debug("Setting current record entry: %s" % key)
        self.transitions[key] = (te[0], entry)

    def _onNewEntryAdded(self, entry):
        pass

