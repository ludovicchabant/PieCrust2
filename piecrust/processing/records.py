import os.path
import hashlib
from piecrust.records import Record, TransitionalRecord


class ProcessorPipelineRecord(Record):
    RECORD_VERSION = 6

    def __init__(self):
        super(ProcessorPipelineRecord, self).__init__()
        self.out_dir = None
        self.process_time = None
        self.processed_count = 0
        self.success = False


FLAG_NONE = 0
FLAG_PREPARED = 2**0
FLAG_PROCESSED = 2**1
FLAG_BYPASSED_STRUCTURED_PROCESSING = 2**3
FLAG_COLLAPSED_FROM_LAST_RUN = 2**4


def _get_transition_key(path):
    return hashlib.md5(path.encode('utf8')).hexdigest()


class ProcessorPipelineRecordEntry(object):
    def __init__(self, path):
        self.path = path

        self.flags = FLAG_NONE
        self.rel_outputs = []
        self.proc_tree = None
        self.errors = []

    @property
    def was_prepared(self):
        return bool(self.flags & FLAG_PREPARED)

    @property
    def was_processed(self):
        return (self.was_prepared and
                (bool(self.flags & FLAG_PROCESSED) or len(self.errors) > 0))

    @property
    def was_processed_successfully(self):
        return self.was_processed and not self.errors

    @property
    def was_collapsed_from_last_run(self):
        return self.flags & FLAG_COLLAPSED_FROM_LAST_RUN


class TransitionalProcessorPipelineRecord(TransitionalRecord):
    def __init__(self, previous_path=None):
        super(TransitionalProcessorPipelineRecord, self).__init__(
                ProcessorPipelineRecord, previous_path)

    def getTransitionKey(self, entry):
        return _get_transition_key(entry.path)

    def getCurrentEntry(self, path):
        key = _get_transition_key(path)
        pair = self.transitions.get(key)
        if pair is not None:
            return pair[1]
        return None

    def getPreviousEntry(self, path):
        key = _get_transition_key(path)
        pair = self.transitions.get(key)
        if pair is not None:
            return pair[0]
        return None

    def collapseRecords(self):
        for prev, cur in self.transitions.values():
            if prev and cur and not cur.was_processed:
                # This asset wasn't processed, so the information from
                # last time is still valid.
                cur.flags = prev.flags | FLAG_COLLAPSED_FROM_LAST_RUN
                cur.rel_outputs = list(prev.rel_outputs)
                cur.errors = list(prev.errors)

    def getDeletions(self):
        for prev, cur in self.transitions.values():
            if prev and not cur:
                for p in prev.rel_outputs:
                    abs_p = os.path.join(self.previous.out_dir, p)
                    yield (abs_p, 'previous asset was removed')
            elif prev and cur and cur.was_processed_successfully:
                diff = set(prev.rel_outputs) - set(cur.rel_outputs)
                for p in diff:
                    abs_p = os.path.join(self.previous.out_dir, p)
                    yield (abs_p, 'asset changed outputs')

