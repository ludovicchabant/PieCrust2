import copy
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
    RECORD_VERSION = 12

    def __init__(self):
        super(BakeRecord, self).__init__()
        self.out_dir = None
        self.bake_time = None
        self.success = True


class BakeRecordPassInfo(object):
    def __init__(self):
        self.used_source_names = set()
        self.used_taxonomy_terms = set()


class BakeRecordSubPageEntry(object):
    FLAG_NONE = 0
    FLAG_BAKED = 2**0
    FLAG_FORCED_BY_SOURCE = 2**1
    FLAG_FORCED_BY_NO_PREVIOUS = 2**2
    FLAG_FORCED_BY_PREVIOUS_ERRORS = 2**3
    FLAG_FORMATTING_INVALIDATED = 2**4

    def __init__(self, out_uri, out_path):
        self.out_uri = out_uri
        self.out_path = out_path
        self.flags = self.FLAG_NONE
        self.errors = []
        self.render_passes = {}

    @property
    def was_clean(self):
        return (self.flags & self.FLAG_BAKED) == 0 and len(self.errors) == 0

    @property
    def was_baked(self):
        return (self.flags & self.FLAG_BAKED) != 0

    @property
    def was_baked_successfully(self):
        return self.was_baked and len(self.errors) == 0

    def collapseRenderPasses(self, other):
        for p, pinfo in self.render_passes.items():
            if p not in other.render_passes:
                other.render_passes[p] = copy.deepcopy(pinfo)


class BakeRecordPageEntry(object):
    """ An entry in the bake record.

        The `taxonomy_info` attribute should be a tuple of the form:
        (taxonomy name, term, source name)
    """
    FLAG_NONE = 0
    FLAG_NEW = 2**0
    FLAG_SOURCE_MODIFIED = 2**1
    FLAG_OVERRIDEN = 2**2

    def __init__(self, source_name, rel_path, path, taxonomy_info=None):
        self.source_name = source_name
        self.rel_path = rel_path
        self.path = path
        self.taxonomy_info = taxonomy_info
        self.flags = self.FLAG_NONE
        self.config = None
        self.subs = []
        self.assets = []
        self.errors = []

    @property
    def path_mtime(self):
        return os.path.getmtime(self.path)

    @property
    def was_overriden(self):
        return (self.flags & self.FLAG_OVERRIDEN) != 0

    @property
    def num_subs(self):
        return len(self.subs)

    @property
    def was_any_sub_baked(self):
        for o in self.subs:
            if o.was_baked:
                return True
        return False

    def getSub(self, sub_index):
        return self.subs[sub_index - 1]

    def getAllErrors(self):
        for o in self.subs:
            yield from o.errors

    def getAllUsedSourceNames(self):
        res = set()
        for o in self.subs:
            for p, pinfo in o.render_passes.items():
                res |= pinfo.used_source_names
        return res

    def getAllUsedTaxonomyTerms(self):
        res = set()
        for o in self.subs:
            for p, pinfo in o.render_passes.items():
                res |= pinfo.used_taxonomy_terms
        return res


class TransitionalBakeRecord(TransitionalRecord):
    def __init__(self, previous_path=None):
        super(TransitionalBakeRecord, self).__init__(BakeRecord,
                                                     previous_path)
        self.dirty_source_names = set()

    def addEntry(self, entry):
        if (self.previous.bake_time and
                entry.path_mtime >= self.previous.bake_time):
            entry.flags |= BakeRecordPageEntry.FLAG_SOURCE_MODIFIED
            self.dirty_source_names.add(entry.source_name)
        super(TransitionalBakeRecord, self).addEntry(entry)

    def getTransitionKey(self, entry):
        return _get_transition_key(entry.source_name, entry.rel_path,
                                   entry.taxonomy_info)

    def getOverrideEntry(self, factory, uri):
        for pair in self.transitions.values():
            cur = pair[1]
            if (cur and
                    (cur.source_name != factory.source.name or
                        cur.rel_path != factory.rel_path)):
                    for o in cur.subs:
                        if o.out_uri == uri:
                            return cur
        return None

    def getPreviousEntry(self, source_name, rel_path, taxonomy_info=None):
        key = _get_transition_key(source_name, rel_path, taxonomy_info)
        pair = self.transitions.get(key)
        if pair is not None:
            return pair[0]
        return None

    def collapseEntry(self, prev_entry):
        cur_entry = copy.deepcopy(prev_entry)
        cur_entry.flags = BakeRecordPageEntry.FLAG_NONE
        for o in cur_entry.subs:
            o.flags = BakeRecordSubPageEntry.FLAG_NONE
        self.addEntry(cur_entry)

    def getDeletions(self):
        for prev, cur in self.transitions.values():
            if prev and not cur:
                for sub in prev.subs:
                    yield (sub.out_path, 'previous source file was removed')
            elif prev and cur:
                prev_out_paths = [o.out_path for o in prev.subs]
                cur_out_paths = [o.out_path for o in cur.subs]
                diff = set(prev_out_paths) - set(cur_out_paths)
                for p in diff:
                    yield (p, 'source file changed outputs')

    def _onNewEntryAdded(self, entry):
        entry.flags |= BakeRecordPageEntry.FLAG_NEW

