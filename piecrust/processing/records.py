import os.path
from piecrust.records import Record, TransitionalRecord


class ProcessorPipelineRecord(Record):
    RECORD_VERSION = 4

    def __init__(self):
        super(ProcessorPipelineRecord, self).__init__()
        self.out_dir = None
        self.process_time = None
        self.success = False

    def hasOverrideEntry(self, rel_path):
        return self.findEntry(rel_path) is not None

    def findEntry(self, rel_path):
        rel_path = rel_path.lower()
        for entry in self.entries:
            for out_path in entry.rel_outputs:
                if out_path.lower() == rel_path:
                    return entry
        return None

    def replaceEntry(self, new_entry):
        for e in self.entries:
            if (e.base_dir == new_entry.base_dir and
                    e.rel_input == new_entry.rel_input):
                e.flags = new_entry.flags
                e.rel_outputs = list(new_entry.rel_outputs)
                e.errors = list(new_entry.errors)
                break


FLAG_NONE = 0
FLAG_PREPARED = 2**0
FLAG_PROCESSED = 2**1
FLAG_OVERRIDEN = 2**2
FLAG_BYPASSED_STRUCTURED_PROCESSING = 2**3


class ProcessorPipelineRecordEntry(object):
    def __init__(self, base_dir, rel_input):
        self.base_dir = base_dir
        self.rel_input = rel_input

        self.flags = FLAG_NONE
        self.rel_outputs = []
        self.proc_tree = None
        self.errors = []

    @property
    def path(self):
        return os.path.join(self.base_dir, self.rel_input)

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


class TransitionalProcessorPipelineRecord(TransitionalRecord):
    def __init__(self, previous_path=None):
        super(TransitionalProcessorPipelineRecord, self).__init__(
                ProcessorPipelineRecord, previous_path)

    def getTransitionKey(self, entry):
        return entry.rel_input

    def getPreviousEntry(self, rel_path):
        pair = self.transitions.get(rel_path)
        if pair is not None:
            return pair[0]
        return None

    def collapseRecords(self):
        for prev, cur in self.transitions.values():
            if prev and cur and not cur.was_processed:
                # This asset wasn't processed, so the information from
                # last time is still valid.
                cur.flags = prev.flags
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

