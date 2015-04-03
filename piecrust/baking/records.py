import os.path
import logging
from piecrust.records import Record, TransitionalRecord


logger = logging.getLogger(__name__)


def _get_transition_key(source_name, rel_path, taxonomy_info=None):
    key = '%s:%s' % (source_name, rel_path)
    if taxonomy_info:
        taxonomy_name, taxonomy_term, taxonomy_source_name = taxonomy_info
        key += ';%s:%s=' % (taxonomy_source_name, taxonomy_name)
        if isinstance(taxonomy_term, tuple):
            key += '/'.join(taxonomy_term)
        else:
            key += taxonomy_term
    return key


class BakeRecord(Record):
    RECORD_VERSION = 11

    def __init__(self):
        super(BakeRecord, self).__init__()
        self.out_dir = None
        self.bake_time = None
        self.success = True


FLAG_NONE = 0
FLAG_SOURCE_MODIFIED = 2**0
FLAG_OVERRIDEN = 2**1
FLAG_FORCED_BY_SOURCE = 2**2


class BakeRecordPageEntry(object):
    """ An entry in the bake record.

        The `taxonomy_info` attribute should be a tuple of the form:
        (taxonomy name, term, source name)
    """
    def __init__(self, source_name, rel_path, path, taxonomy_info=None):
        self.source_name = source_name
        self.rel_path = rel_path
        self.path = path
        self.taxonomy_info = taxonomy_info

        self.flags = FLAG_NONE
        self.config = None
        self.errors = []
        self.out_uris = []
        self.out_paths = []
        self.clean_uris = []
        self.clean_out_paths = []
        self.used_source_names = set()
        self.used_taxonomy_terms = set()
        self.used_pagination_item_count = 0

    @property
    def path_mtime(self):
        return os.path.getmtime(self.path)

    @property
    def was_baked(self):
        return len(self.out_paths) > 0 or len(self.errors) > 0

    @property
    def was_baked_successfully(self):
        return len(self.out_paths) > 0 and len(self.errors) == 0

    @property
    def num_subs(self):
        return len(self.out_paths)


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
                                   entry.taxonomy_info)

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

    def getPreviousEntry(self, source_name, rel_path, taxonomy_info=None):
        key = _get_transition_key(source_name, rel_path, taxonomy_info)
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

