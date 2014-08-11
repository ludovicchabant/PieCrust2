import logging
from piecrust.records import Record


logger = logging.getLogger(__name__)


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
    VERSION = 1

    def __init__(self):
        super(BakeRecord, self).__init__()
        self.out_dir = None
        self.bake_time = None


class BakeRecordPageEntry(object):
    def __init__(self, page):
        self.path = page.path
        self.rel_path = page.rel_path
        self.source_name = page.source.name
        self.config = page.config.get()
        self.taxonomy_name = None
        self.taxonomy_term = None
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

class TransitionalBakeRecord(object):
    DELETION_MISSING = 1
    DELETION_CHANGED = 2

    def __init__(self, previous_path=None):
        self.previous = BakeRecord()
        self.current = BakeRecord()
        self.transitions = {}
        if previous_path:
            self.loadPrevious(previous_path)
        self.current.entry_added += self._onCurrentEntryAdded

    def loadPrevious(self, previous_path):
        self.previous = BakeRecord.load(previous_path)
        for e in self.previous.entries:
            self.transitions[e.transition_key] = (e, None)

    def saveCurrent(self, current_path):
        self.current.save(current_path)

    def addEntry(self, entry):
        self.current.addEntry(entry)

    def getPreviousEntry(self, page, taxonomy_name=None, taxonomy_term=None):
        key = _get_transition_key(page.source.name, page.rel_path,
                taxonomy_name, taxonomy_term)
        pair = self.transitions.get(key)
        if pair is not None:
            return pair[0]
        return None

    def collapseRecords(self):
        for pair in self.transitions.itervalues():
            prev = pair[0]
            cur = pair[1]

            if prev and cur and not cur.was_baked:
                # This page wasn't baked, so the information from last
                # time is still valid (we didn't get any information
                # since we didn't bake).
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

