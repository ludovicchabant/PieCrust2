import copy
from piecrust.pipelines.records import RecordEntry


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

    def __init__(self):
        super().__init__()
        self.flags = self.FLAG_NONE
        self.config = None
        self.subs = []

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
    def all_assets(self):
        for sub in self.subs:
            yield from sub.assets

    @property
    def all_out_paths(self):
        for sub in self.subs:
            yield sub.out_path

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

