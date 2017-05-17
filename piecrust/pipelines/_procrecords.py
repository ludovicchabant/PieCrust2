from piecrust.pipelines.records import RecordEntry


class AssetPipelineRecordEntry(RecordEntry):
    FLAG_NONE = 0
    FLAG_PREPARED = 2**0
    FLAG_PROCESSED = 2**1
    FLAG_BYPASSED_STRUCTURED_PROCESSING = 2**3
    FLAG_COLLAPSED_FROM_LAST_RUN = 2**4

    def __init__(self):
        super().__init__()
        self.out_paths = []
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


