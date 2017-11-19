from piecrust.pipelines.records import (
    RecordEntry, get_flag_descriptions)


class AssetPipelineRecordEntry(RecordEntry):
    FLAG_NONE = 0
    FLAG_PREPARED = 2**0
    FLAG_PROCESSED = 2**1
    FLAG_BYPASSED_STRUCTURED_PROCESSING = 2**3
    FLAG_COLLAPSED_FROM_LAST_RUN = 2**4

    def __init__(self):
        super().__init__()
        self.flags = self.FLAG_NONE
        self.proc_tree = None
        self.out_paths = []

    @property
    def was_prepared(self):
        return bool(self.flags & self.FLAG_PREPARED)

    @property
    def was_processed(self):
        return (self.was_prepared and
                (bool(self.flags & self.FLAG_PROCESSED) or
                 len(self.errors) > 0))

    @property
    def was_processed_successfully(self):
        return self.was_processed and not self.errors

    @property
    def was_collapsed_from_last_run(self):
        return self.flags & self.FLAG_COLLAPSED_FROM_LAST_RUN

    def describe(self):
        d = super().describe()
        d['Flags'] = get_flag_descriptions(self.flags, flag_descriptions)
        d['Processing Tree'] = _format_proc_tree(self.proc_tree, 20 * ' ')
        return d

    def getAllOutputPaths(self):
        return self.out_paths


def add_asset_job_result(result):
    result.update({
        'item_spec': None,
        'flags': AssetPipelineRecordEntry.FLAG_NONE,
        'proc_tree': None,
        'out_paths': [],
    })


def merge_job_result_into_record_entry(record_entry, result):
    record_entry.item_spec = result['item_spec']
    record_entry.flags |= result['flags']
    record_entry.proc_tree = result['proc_tree']
    record_entry.out_paths = result['out_paths']


flag_descriptions = {
    AssetPipelineRecordEntry.FLAG_PREPARED: 'prepared',
    AssetPipelineRecordEntry.FLAG_PROCESSED: 'processed',
    AssetPipelineRecordEntry.FLAG_BYPASSED_STRUCTURED_PROCESSING: 'external',
    AssetPipelineRecordEntry.FLAG_COLLAPSED_FROM_LAST_RUN: 'from last run'}


def _format_proc_tree(tree, margin='', level=0):
    name, children = tree
    res = '%s%s+ %s\n' % (margin if level > 0 else '', level * '  ', name)
    if children:
        for c in children:
            res += _format_proc_tree(c, margin, level + 1)
    return res

