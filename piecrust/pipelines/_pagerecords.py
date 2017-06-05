import copy
from piecrust.pipelines.records import RecordEntry, get_flag_descriptions


class SubPagePipelineRecordEntry:
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
        self.render_info = [None, None]  # Same length as RENDER_PASSES

    @property
    def was_clean(self):
        return (self.flags & self.FLAG_BAKED) == 0 and len(self.errors) == 0

    @property
    def was_baked(self):
        return (self.flags & self.FLAG_BAKED) != 0

    @property
    def was_baked_successfully(self):
        return self.was_baked and len(self.errors) == 0

    def anyPass(self, func):
        for pinfo in self.render_info:
            if pinfo and func(pinfo):
                return True
        return False

    def copyRenderInfo(self):
        return copy.deepcopy(self.render_info)


class PagePipelineRecordEntry(RecordEntry):
    FLAG_NONE = 0
    FLAG_NEW = 2**0
    FLAG_SOURCE_MODIFIED = 2**1
    FLAG_OVERRIDEN = 2**2
    FLAG_COLLAPSED_FROM_LAST_RUN = 2**3

    def __init__(self):
        super().__init__()
        self.flags = self.FLAG_NONE
        self.config = None
        self.subs = []

    @property
    def was_touched(self):
        return (self.flags & self.FLAG_SOURCE_MODIFIED) != 0

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

    @property
    def has_any_error(self):
        if len(self.errors) > 0:
            return True
        for o in self.subs:
            if len(o.errors) > 0:
                return True
        return False

    def getSub(self, page_num):
        return self.subs[page_num - 1]

    def getAllErrors(self):
        yield from self.errors
        for o in self.subs:
            yield from o.errors

    def getAllUsedSourceNames(self):
        res = set()
        for o in self.subs:
            for pinfo in o.render_info:
                if pinfo:
                    res |= pinfo.used_source_names
        return res

    def getAllOutputPaths(self):
        for o in self.subs:
            yield o.out_path

    def describe(self):
        d = super().describe()
        d['Flags'] = get_flag_descriptions(self.flags, flag_descriptions)
        for i, sub in enumerate(self.subs):
            d['Sub%02d' % i] = {
                'URI': sub.out_uri,
                'Path': sub.out_path,
                'Flags': get_flag_descriptions(
                    sub.flags, sub_flag_descriptions)
            }
        return d


flag_descriptions = {
    PagePipelineRecordEntry.FLAG_NEW: 'new',
    PagePipelineRecordEntry.FLAG_SOURCE_MODIFIED: 'touched',
    PagePipelineRecordEntry.FLAG_OVERRIDEN: 'overriden',
    PagePipelineRecordEntry.FLAG_COLLAPSED_FROM_LAST_RUN: 'from last run'}


sub_flag_descriptions = {
    SubPagePipelineRecordEntry.FLAG_BAKED: 'baked',
    SubPagePipelineRecordEntry.FLAG_FORCED_BY_SOURCE: 'forced by source',
    SubPagePipelineRecordEntry.FLAG_FORCED_BY_NO_PREVIOUS: 'forced b/c new',
    SubPagePipelineRecordEntry.FLAG_FORCED_BY_PREVIOUS_ERRORS:
    'forced by errors',
    SubPagePipelineRecordEntry.FLAG_FORMATTING_INVALIDATED:
    'formatting invalidated'
}
