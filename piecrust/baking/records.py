import os.path
import logging
from piecrust import APP_VERSION
from piecrust.sources.base import PageSource
from piecrust.records import Record


logger = logging.getLogger(__name__)


RECORD_VERSION = 4


def _get_transition_key(source_name, rel_path, taxonomy_name=None,
        taxonomy_term=None):
    key = '%s:%s' % (source_name, rel_path)
    if taxonomy_name and taxonomy_term:
        key += ';%s:' % taxonomy_name
        if isinstance(taxonomy_term, tuple):
            key += '/'.join(taxonomy_term)
        else:
            key += taxonomy_term
    return key


class BakeRecord(Record):
    def __init__(self):
        super(BakeRecord, self).__init__()
        self.out_dir = None
        self.bake_time = None
        self.app_version = APP_VERSION
        self.record_version = RECORD_VERSION

    def hasLatestVersion(self):
        return (self.app_version == APP_VERSION and
                self.record_version == RECORD_VERSION)

    def __setstate__(self, state):
        state.setdefault('app_version', -1)
        state.setdefault('record_version', -1)
        super(BakeRecord, self).__setstate__(state)


FLAG_NONE = 0
FLAG_SOURCE_MODIFIED = 2**0
FLAG_OVERRIDEN = 2**1


class BakeRecordPageEntry(object):
    def __init__(self, factory, taxonomy_name=None, taxonomy_term=None):
        self.path = factory.path
        self.rel_path = factory.rel_path
        self.source_name = factory.source.name
        self.taxonomy_name = taxonomy_name
        self.taxonomy_term = taxonomy_term
        self.path_mtime = os.path.getmtime(factory.path)

        self.flags = FLAG_NONE
        self.config = None
        self.out_uris = []
        self.out_paths = []
        self.used_source_names = set()
        self.used_taxonomy_terms = set()

    @property
    def was_baked(self):
        return len(self.out_paths) > 0

    @property
    def num_subs(self):
        return len(self.out_paths)

    @property
    def transition_key(self):
        return _get_transition_key(self.source_name, self.rel_path,
                self.taxonomy_name, self.taxonomy_term)

    def addUsedSource(self, source):
        if isinstance(source, PageSource):
            self.used_source_names.add(source.name)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['path_mtime']
        return state


class TransitionalBakeRecord(object):
    DELETION_MISSING = 1
    DELETION_CHANGED = 2

    def __init__(self, previous_path=None):
        self.previous = BakeRecord()
        self.current = BakeRecord()
        self.transitions = {}
        self.incremental_count = 0
        if previous_path:
            self.loadPrevious(previous_path)
        self.current.entry_added += self._onCurrentEntryAdded

    def loadPrevious(self, previous_path):
        try:
            self.previous = BakeRecord.load(previous_path)
        except Exception as ex:
            logger.debug("Error loading previous record: %s" % ex)
            logger.debug("Will reset to an empty one.")
            self.previous = BakeRecord()
            return

        for e in self.previous.entries:
            self.transitions[e.transition_key] = (e, None)

    def saveCurrent(self, current_path):
        self.current.save(current_path)

    def addEntry(self, entry):
        if (self.previous.bake_time and
                entry.path_mtime >= self.previous.bake_time):
            entry.flags |= FLAG_SOURCE_MODIFIED
        self.current.addEntry(entry)

    def getOverrideEntry(self, factory, uri):
        for pair in self.transitions.values():
            prev = pair[0]
            cur = pair[1]
            if (cur and
                    (cur.source_name != factory.source.name or
                        cur.rel_path != factory.rel_path) and
                    len(cur.out_uris) > 0 and cur.out_uris[0] == uri):
                return cur
            if (prev and
                    (prev.source_name != factory.source.name or
                        prev.rel_path != factory.rel_path) and
                    len(prev.out_uris) > 0 and prev.out_uris[0] == uri):
                return prev
        return None

    def getPreviousEntry(self, source_name, rel_path, taxonomy_name=None,
            taxonomy_term=None):
        key = _get_transition_key(source_name, rel_path,
                taxonomy_name, taxonomy_term)
        pair = self.transitions.get(key)
        if pair is not None:
            return pair[0]
        return None

    def getCurrentEntries(self, source_name):
        return [e for e in self.current.entries
                if e.source_name == source_name]

    def collapseRecords(self):
        for pair in self.transitions.values():
            prev = pair[0]
            cur = pair[1]

            if prev and cur and not cur.was_baked:
                # This page wasn't baked, so the information from last
                # time is still valid (we didn't get any information
                # since we didn't bake).
                cur.flags = prev.flags
                if prev.config:
                    cur.config = prev.config.copy()
                cur.out_uris = list(prev.out_uris)
                cur.out_paths = list(prev.out_paths)
                cur.used_source_names = set(prev.used_source_names)
                cur.used_taxonomy_terms = set(prev.used_taxonomy_terms)

    def _onCurrentEntryAdded(self, entry):
        key = entry.transition_key
        te = self.transitions.get(key)
        if te is None:
            logger.debug("Adding new record entry: %s" % key)
            self.transitions[key] = (None, entry)
            return

        if te[1] is not None:
            raise Exception("A current entry already exists for: %s" %
                    key)
        logger.debug("Setting current record entry: %s" % key)
        self.transitions[key] = (te[0], entry)

