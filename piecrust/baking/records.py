import os.path
import logging
from piecrust.sources.base import PageSource
from piecrust.records import Record, TransitionalRecord


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
    RECORD_VERSION = 9

    def __init__(self):
        super(BakeRecord, self).__init__()
        self.out_dir = None
        self.bake_time = None
        self.success = True


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
        self.errors = []
        self.out_uris = []
        self.out_paths = []
        self.used_source_names = set()
        self.used_taxonomy_terms = set()

    @property
    def was_baked(self):
        return len(self.out_paths) > 0 or len(self.errors) > 0

    @property
    def was_baked_successfully(self):
        return len(self.out_paths) > 0 and len(self.errors) == 0

    @property
    def num_subs(self):
        return len(self.out_paths)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['path_mtime']
        return state


class TransitionalBakeRecord(TransitionalRecord):
    def __init__(self, previous_path=None):
        super(TransitionalBakeRecord, self).__init__(BakeRecord,
                                                     previous_path)

    def addEntry(self, entry):
        if (self.previous.bake_time and
                entry.path_mtime >= self.previous.bake_time):
            entry.flags |= FLAG_SOURCE_MODIFIED
        super(TransitionalBakeRecord, self).addEntry(entry)

    def getTransitionKey(self, entry):
        return _get_transition_key(entry.source_name, entry.rel_path,
                                   entry.taxonomy_name, entry.taxonomy_term)

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
        for prev, cur in self.transitions.values():
            if prev and cur and not cur.was_baked:
                # This page wasn't baked, so the information from last
                # time is still valid (we didn't get any information
                # since we didn't bake).
                cur.flags = prev.flags
                if prev.config:
                    cur.config = prev.config.copy()
                cur.out_uris = list(prev.out_uris)
                cur.out_paths = list(prev.out_paths)
                cur.errors = list(prev.errors)
                cur.used_source_names = set(prev.used_source_names)
                cur.used_taxonomy_terms = set(prev.used_taxonomy_terms)

    def getDeletions(self):
        for prev, cur in self.transitions.values():
            if prev and not cur:
                for p in prev.out_paths:
                    yield (p, 'previous source file was removed')
            elif prev and cur and cur.was_baked_successfully:
                diff = set(prev.out_paths) - set(cur.out_paths)
                for p in diff:
                    yield (p, 'source file changed outputs')

