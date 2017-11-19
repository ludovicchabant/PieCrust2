import os
import os.path
import pickle
import hashlib
import logging
from piecrust import APP_VERSION


logger = logging.getLogger(__name__)


class RecordEntry:
    """ An entry in a record, for a specific content item.
    """
    def __init__(self):
        self.item_spec = None
        self.errors = []

    @property
    def success(self):
        return len(self.errors) == 0

    def describe(self):
        return {}

    def getAllOutputPaths(self):
        return None

    def getAllErrors(self):
        return self.errors


class Record:
    """ A class that represents a 'record' of a bake operation on a
        content source.
    """
    def __init__(self, name):
        self.name = name
        self.deleted_out_paths = []
        self.user_data = {}
        self.success = True
        self._entries = {}

    @property
    def entry_count(self):
        return len(self._entries)

    def addEntry(self, entry):
        if entry.item_spec in self._entries:
            raise ValueError("Entry '%s' is already in the record." %
                             entry.item_spec)
        self._entries[entry.item_spec] = entry

    def getEntries(self):
        return self._entries.values()

    def getEntry(self, item_spec):
        return self._entries.get(item_spec)


class MultiRecord:
    """ A container that includes multiple `Record` instances -- one for
        each content source that was baked.
    """
    RECORD_VERSION = 13

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
            raise Exception("No such record: %s" % record_name)
        record = Record(record_name)
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


def get_flag_descriptions(flags, flag_descriptions):
    res = []
    for k, v in flag_descriptions.items():
        if flags & k:
            res.append(v)
    if res:
        return ', '.join(res)
    return 'none'


def _are_records_valid(multi_record):
    return (multi_record._app_version == APP_VERSION and
            multi_record._record_version == MultiRecord.RECORD_VERSION)


def load_records(path, raise_errors=False):
    try:
        multi_record = MultiRecord.load(path)
    except FileNotFoundError:
        if raise_errors:
            raise
        logger.debug("No existing records found at: %s" % path)
        multi_record = None
    except Exception as ex:
        if raise_errors:
            raise
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


class RecordHistory:
    def __init__(self, previous, current):
        if previous is None or current is None:
            raise ValueError()

        if previous.name != current.name:
            raise Exception("The two records must have the same name! "
                            "Got '%s' and '%s'." %
                            (previous.name, current.name))

        self._previous = previous
        self._current = current
        self._diffs = None

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
        if self._diffs is None:
            raise Exception("This record history hasn't been built yet.")
        return self._diffs.values()

    def getPreviousEntry(self, item_spec):
        key = _build_diff_key(item_spec)
        return self._diffs[key][0]

    def getCurrentEntry(self, item_spec):
        key = _build_diff_key(item_spec)
        return self._diffs[key][1]

    def build(self):
        if self._diffs is not None:
            raise Exception("This record history has already been built.")

        self._diffs = {}
        if self._previous is not None:
            for e in self._previous.getEntries():
                key = _build_diff_key(e.item_spec)
                self._diffs[key] = (e, None)

        if self._current is not None:
            for e in self._current.getEntries():
                key = _build_diff_key(e.item_spec)
                diff = self._diffs.get(key)
                if diff is None:
                    self._diffs[key] = (None, e)
                elif diff[1] is None:
                    self._diffs[key] = (diff[0], e)
                else:
                    raise Exception(
                        "A current record entry already exists for '%s' "
                        "(%s)" % (key, diff[1].item_spec))

    def copy(self):
        return RecordHistory(self._previous, self._current)


class MultiRecordHistory:
    """ Tracks the differences between an 'old' and a 'new' record
        container.
    """
    def __init__(self, previous, current):
        if previous is None or current is None:
            raise ValueError()

        self.previous = previous
        self.current = current
        self.histories = []
        self._linkHistories(previous, current)

    def getPreviousRecord(self, record_name, auto_create=True):
        return self.previous.getRecord(record_name, auto_create=auto_create)

    def getCurrentRecord(self, record_name):
        return self.current.getRecord(record_name)

    def getHistory(self, record_name):
        for h in self.histories:
            if h.name == record_name:
                return h

        rh = RecordHistory(
            Record(record_name),
            Record(record_name))
        self.histories.append(rh)
        self.previous.records.append(rh.previous)
        self.current.records.append(rh.current)
        return rh

    def _linkHistories(self, previous, current):
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

        for name, pair in pairs.items():
            p, c = pair
            if p is None:
                p = Record(name)
                previous.records.append(p)
            if c is None:
                c = Record(name)
                current.records.append(c)
            self.histories.append(RecordHistory(p, c))


def _build_diff_key(item_spec):
    return hashlib.md5(item_spec.encode('utf8')).hexdigest()

