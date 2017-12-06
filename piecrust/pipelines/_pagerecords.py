import copy
from piecrust.pipelines.records import RecordEntry, get_flag_descriptions


class SubPageFlags:
    FLAG_NONE = 0
    FLAG_BAKED = 2**0
    FLAG_FORCED_BY_SOURCE = 2**1
    FLAG_FORCED_BY_NO_PREVIOUS = 2**2
    FLAG_FORCED_BY_PREVIOUS_ERRORS = 2**3
    FLAG_FORCED_BY_GENERAL_FORCE = 2**4
    FLAG_RENDER_CACHE_INVALIDATED = 2**5
    FLAG_COLLAPSED_FROM_LAST_RUN = 2**6


def create_subpage_job_result(out_uri, out_path):
    return {
        'out_uri': out_uri,
        'out_path': out_path,
        'flags': SubPageFlags.FLAG_NONE,
        'errors': [],
        'render_info': None
    }


def was_subpage_clean(sub):
    return ((sub['flags'] & SubPageFlags.FLAG_BAKED) == 0 and
            len(sub['errors']) == 0)


def was_subpage_baked(sub):
    return (sub['flags'] & SubPageFlags.FLAG_BAKED) != 0


def was_subpage_baked_successfully(sub):
    return was_subpage_baked(sub) and len(sub['errors']) == 0


class PagePipelineRecordEntry(RecordEntry):
    FLAG_NONE = 0
    FLAG_NEW = 2**0
    FLAG_SOURCE_MODIFIED = 2**1
    FLAG_OVERRIDEN = 2**2
    FLAG_COLLAPSED_FROM_LAST_RUN = 2**3
    FLAG_IS_DRAFT = 2**4
    FLAG_ABORTED_FOR_SOURCE_USE = 2**5

    def __init__(self):
        super().__init__()
        self.flags = self.FLAG_NONE
        self.config = None
        self.route_params = None
        self.timestamp = None
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
            if was_subpage_baked(o):
                return True
        return False

    @property
    def has_any_error(self):
        if len(self.errors) > 0:
            return True
        for o in self.subs:
            if len(o['errors']) > 0:
                return True
        return False

    def getSub(self, page_num):
        return self.subs[page_num - 1]

    def getAllErrors(self):
        yield from self.errors
        for o in self.subs:
            yield from o['errors']

    def getAllUsedSourceNames(self):
        res_segments = set()
        res_layout = set()
        for o in self.subs:
            pinfo = o.get('render_info')
            if pinfo:
                usn = pinfo['used_source_names']
                res_segments |= set(usn['segments'])
                res_layout |= set(usn['layout'])
        return res_segments, res_layout

    def getAllOutputPaths(self):
        for o in self.subs:
            yield o['out_path']

    def describe(self):
        d = super().describe()
        d['Flags'] = get_flag_descriptions(self.flags, flag_descriptions)
        for i, sub in enumerate(self.subs):
            d['Sub%02d' % i] = {
                'URI': sub['out_uri'],
                'Path': sub['out_path'],
                'Flags': get_flag_descriptions(
                    sub['flags'], sub_flag_descriptions),
                'RenderInfo': _describe_render_info(sub['render_info'])
            }
        return d


def add_page_job_result(result):
    result.update({
        'flags': PagePipelineRecordEntry.FLAG_NONE,
        'errors': [],
        'subs': []
    })


def merge_job_result_into_record_entry(record_entry, result):
    record_entry.flags |= result['flags']
    record_entry.errors += result['errors']
    record_entry.subs += result['subs']


flag_descriptions = {
    PagePipelineRecordEntry.FLAG_NEW: 'new',
    PagePipelineRecordEntry.FLAG_SOURCE_MODIFIED: 'touched',
    PagePipelineRecordEntry.FLAG_OVERRIDEN: 'overriden',
    PagePipelineRecordEntry.FLAG_COLLAPSED_FROM_LAST_RUN: 'from last run',
    PagePipelineRecordEntry.FLAG_IS_DRAFT: 'draft',
    PagePipelineRecordEntry.FLAG_ABORTED_FOR_SOURCE_USE: 'aborted for source use'}


sub_flag_descriptions = {
    SubPageFlags.FLAG_BAKED: 'baked',
    SubPageFlags.FLAG_FORCED_BY_SOURCE: 'forced by source',
    SubPageFlags.FLAG_FORCED_BY_NO_PREVIOUS: 'forced b/c new',
    SubPageFlags.FLAG_FORCED_BY_PREVIOUS_ERRORS: 'forced by errors',
    SubPageFlags.FLAG_FORCED_BY_GENERAL_FORCE: 'manually forced',
    SubPageFlags.FLAG_RENDER_CACHE_INVALIDATED: 'cache invalidated',
    SubPageFlags.FLAG_COLLAPSED_FROM_LAST_RUN: 'from last run'
}


def _describe_render_info(ri):
    if ri is None:
        return '<null>'
    return {
        'UsedPagination': ri['used_pagination'],
        'PaginationHasMore': ri['pagination_has_more'],
        'UsedAssets': ri['used_assets'],
        'UsedSourceNames': ri['used_source_names']
    }
