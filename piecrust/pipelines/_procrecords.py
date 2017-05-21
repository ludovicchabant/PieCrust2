from piecrust.pipelines.records import RecordEntry


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
        d['Flags'] = _get_flag_descriptions(self.flags)
        d['Processing Tree'] = _format_proc_tree(self.proc_tree, 20 * ' ')
        return d


flag_descriptions = {
    AssetPipelineRecordEntry.FLAG_PREPARED: 'prepared',
    AssetPipelineRecordEntry.FLAG_PROCESSED: 'processed',
    AssetPipelineRecordEntry.FLAG_BYPASSED_STRUCTURED_PROCESSING: 'external',
    AssetPipelineRecordEntry.FLAG_COLLAPSED_FROM_LAST_RUN: 'from last run'}


def _get_flag_descriptions(flags):
    res = []
    for k, v in flag_descriptions.items():
        if flags & k:
            res.append(v)
    if res:
        return ', '.join(res)
    return 'none'


def _format_proc_tree(tree, margin='', level=0):
    name, children = tree
    res = '%s%s+ %s\n' % (margin if level > 0 else '', level * '  ', name)
    if children:
        for c in children:
            res += _format_proc_tree(c, margin, level + 1)
    return res

