import os
import os.path
import pickle
import hashlib
import logging
from piecrust import APP_VERSION


logger = logging.getLogger(__name__)


class MultiRecord:
    RECORD_VERSION = 12

    def __init__(self):
        self.records = []
        self.success = True
        self.bake_time = 0
        self.incremental_count = 0
        self.invalidated = False
        self.stats = None
        self._app_version = APP_VERSION
        self._record_version = self.RECORD_VERSION

    def getRecord(self, record_name, auto_create=True):
        for r in self.records:
            if r.name == record_name:
                return r
        if not auto_create:
            return None
        record = Record()
        self.records.append(record)
        return record

    def save(self, path):
        path_dir = os.path.dirname(path)
        if not os.path.isdir(path_dir):
            os.makedirs(path_dir, 0o755)

        with open(path, 'wb') as fp:
            pickle.dump(self, fp, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(path):
        logger.debug("Loading bake records from: %s" % path)
        with open(path, 'rb') as fp:
            return pickle.load(fp)


class Record:
    def __init__(self):
        self.name = None
        self.entries = []
        self.stats = {}
        self.out_dir = None
        self.success = True


class RecordEntry:
    def __init__(self):
        self.item_spec = None
        self.errors = []

    @property
    def success(self):
        return len(self.errors) == 0


def _are_records_valid(multi_record):
    return (multi_record._app_version == APP_VERSION and
            multi_record._record_version == MultiRecord.RECORD_VERSION)


def load_records(path):
    try:
        multi_record = MultiRecord.load(path)
    except Exception as ex:
        logger.debug("Error loading records from: %s" % path)
        logger.debug(ex)
        logger.debug("Will use empty records.")
        multi_record = None

    was_invalid = False
    if multi_record is not None and not _are_records_valid(multi_record):
        logger.debug(
            "Records from '%s' have old version: %s/%s." %
            (path, multi_record._app_version, multi_record._record_version))
        logger.debug("Will use empty records.")
        multi_record = None
        was_invalid = True

    if multi_record is None:
        multi_record = MultiRecord()
        multi_record.invalidated = was_invalid

    return multi_record


def _build_diff_key(item_spec):
    return hashlib.md5(item_spec.encode('utf8')).hexdigest()


class MultiRecordHistory:
    def __init__(self, previous, current):
        if previous is None or current is None:
            raise ValueError()

        self.previous = previous
        self.current = current
        self.histories = []
        self._buildHistories(previous, current)

    def getHistory(self, record_name):
        for h in self.histories:
            if h.name == record_name:
                return h
        return None

    def _buildHistories(self, previous, current):
        pairs = {}
        if previous:
            for r in previous.records:
                pairs[r.name] = (r, None)
        if current:
            for r in current.records:
                p = pairs.get(r.name, (None, None))
                if p[1] is not None:
                    raise Exception("Got several records named: %s" % r.name)
                pairs[r.name] = (p[0], r)

        for p, c in pairs.values():
            self.histories.append(RecordHistory(p, c))


class RecordHistory:
    def __init__(self, previous, current):
        self._diffs = {}
        self._previous = previous
        self._current = current

        if previous and current and previous.name != current.name:
            raise Exception("The two records must have the same name! "
                            "Got '%s' and '%s'." %
                            (previous.name, current.name))

        self._buildDiffs()

    @property
    def name(self):
        return self._current.name

    @property
    def current(self):
        return self._current

    @property
    def previous(self):
        return self._previous

    @property
    def diffs(self):
        return self._diffs.values()

    def _buildDiffs(self):
        if self._previous is not None:
            for e in self._previous.entries:
                key = _build_diff_key(e.item_spec)
                self._diffs[key] = (e, None)

        if self._current is not None:
            for e in self._current.entries:
                key = _build_diff_key(e.item_spec)
                diff = self._diffs.get(key)
                if diff is None:
                    self._diffs[key] = (None, e)
                elif diff[1] is None:
                    self._diffs[key] = (diff[0], e)
                else:
                    raise Exception(
                        "A current record entry already exists for: %s" % key)

