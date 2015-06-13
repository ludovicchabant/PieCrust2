import copy
import os.path
import hashlib
import logging
from piecrust.records import Record, TransitionalRecord


logger = logging.getLogger(__name__)


def _get_transition_key(path, taxonomy_info=None):
    key = path
    if taxonomy_info:
        key += '+%s:%s=' % (taxonomy_info.source_name,
                            taxonomy_info.taxonomy_name)
        if isinstance(taxonomy_info.term, tuple):
            key += '/'.join(taxonomy_info.term)
        else:
            key += taxonomy_info.term
    return hashlib.md5(key.encode('utf8')).hexdigest()


class BakeRecord(Record):
    RECORD_VERSION = 14

    def __init__(self):
        super(BakeRecord, self).__init__()
        self.out_dir = None
        self.bake_time = None
        self.timers = None
        self.success = True


class BakePassInfo(object):
    def __init__(self):
        self.used_source_names = set()
        self.used_taxonomy_terms = set()


class SubPageBakeInfo(object):
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


class PageBakeInfo(object):
    def __init__(self):
        self.subs = []
        self.assets = []


class FirstRenderInfo(object):
    def __init__(self):
        self.assets = []
        self.used_pagination = False
        self.pagination_has_more = False


class TaxonomyInfo(object):
    def __init__(self, taxonomy_name, source_name, term):
        self.taxonomy_name = taxonomy_name
        self.source_name = source_name
        self.term = term


class BakeRecordEntry(object):
    """ An entry in the bake record.

        The `taxonomy_info` attribute should be a tuple of the form:
        (taxonomy name, term, source name)
    """
    FLAG_NONE = 0
    FLAG_NEW = 2**0
    FLAG_SOURCE_MODIFIED = 2**1
    FLAG_OVERRIDEN = 2**2

    def __init__(self, source_name, path, taxonomy_info=None):
        self.source_name = source_name
        self.path = path
        self.taxonomy_info = taxonomy_info
        self.flags = self.FLAG_NONE
        self.config = None
        self.errors = []
        self.bake_info = None
        self.first_render_info = None

    @property
    def path_mtime(self):
        return os.path.getmtime(self.path)

    @property
    def was_overriden(self):
        return (self.flags & self.FLAG_OVERRIDEN) != 0

    @property
    def num_subs(self):
        if self.bake_info is None:
            return 0
        return len(self.bake_info.subs)

    @property
    def was_any_sub_baked(self):
        if self.bake_info is not None:
            for o in self.bake_info.subs:
                if o.was_baked:
                    return True
        return False

    @property
    def subs(self):
        if self.bake_info is not None:
            return self.bake_info.subs
        return []

    @property
    def has_any_error(self):
        if len(self.errors) > 0:
            return True
        if self.bake_info is not None:
            for o in self.bake_info.subs:
                if len(o.errors) > 0:
                    return True
        return False

    def getSub(self, sub_index):
        if self.bake_info is None:
            raise Exception("No bake info available on this entry.")
        return self.bake_info.subs[sub_index - 1]

    def getAllErrors(self):
        yield from self.errors
        if self.bake_info is not None:
            for o in self.bake_info.subs:
                yield from o.errors

    def getAllUsedSourceNames(self):
        res = set()
        if self.bake_info is not None:
            for o in self.bake_info.subs:
                for p, pinfo in o.render_passes.items():
                    res |= pinfo.used_source_names
        return res

    def getAllUsedTaxonomyTerms(self):
        res = set()
        if self.bake_info is not None:
            for o in self.bake_info.subs:
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
            entry.flags |= BakeRecordEntry.FLAG_SOURCE_MODIFIED
            self.dirty_source_names.add(entry.source_name)
        super(TransitionalBakeRecord, self).addEntry(entry)

    def getTransitionKey(self, entry):
        return _get_transition_key(entry.path, entry.taxonomy_info)

    def getPreviousAndCurrentEntries(self, path, taxonomy_info=None):
        key = _get_transition_key(path, taxonomy_info)
        pair = self.transitions.get(key)
        return pair

    def getOverrideEntry(self, path, uri):
        for pair in self.transitions.values():
            cur = pair[1]
            if cur and cur.path != path:
                for o in cur.subs:
                    if o.out_uri == uri:
                        return cur
        return None

    def getPreviousEntry(self, path, taxonomy_info=None):
        pair = self.getPreviousAndCurrentEntries(path, taxonomy_info)
        if pair is not None:
            return pair[0]
        return None

    def getCurrentEntry(self, path, taxonomy_info=None):
        pair = self.getPreviousAndCurrentEntries(path, taxonomy_info)
        if pair is not None:
            return pair[1]
        return None

    def collapseEntry(self, prev_entry):
        cur_entry = copy.deepcopy(prev_entry)
        cur_entry.flags = BakeRecordEntry.FLAG_NONE
        for o in cur_entry.subs:
            o.flags = SubPageBakeInfo.FLAG_NONE
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
        entry.flags |= BakeRecordEntry.FLAG_NEW

