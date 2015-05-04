import re
import os.path
import copy
from piecrust.sources.base import PageFactory


page_ref_pattern = re.compile(r'(?P<src>[\w]+)\:(?P<path>.*?)(;|$)')


class PageNotFoundError(Exception):
    pass


class PageRef(object):
    """ A reference to a page, with support for looking a page in different
        realms.
    """
    _INDEX_NEEDS_LOADING = -2
    _INDEX_NOT_FOUND = -1

    class _HitInfo(object):
        def __init__(self, source_name, rel_path, path, metadata):
            self.source_name = source_name
            self.rel_path = rel_path
            self.path = path
            self.metadata = metadata

    def __init__(self, app, page_ref):
        self.app = app
        self._page_ref = page_ref
        self._hits = None
        self._first_valid_hit_index = self._INDEX_NEEDS_LOADING
        self._exts = list(app.config.get('site/auto_formats').keys())

    @property
    def exists(self):
        try:
            self._checkHits()
            return True
        except PageNotFoundError:
            return False

    @property
    def source_name(self):
        self._checkHits()
        return self._first_valid_hit.source_name

    @property
    def source(self):
        return self.app.getSource(self.source_name)

    @property
    def rel_path(self):
        self._checkHits()
        return self._first_valid_hit.rel_path

    @property
    def path(self):
        self._checkHits()
        return self._first_valid_hit.path

    @property
    def metadata(self):
        self._checkHits()
        return self._first_valid_hit.metadata

    @property
    def possible_rel_paths(self):
        self._load()
        return [h.rel_path for h in self._hits]

    @property
    def possible_paths(self):
        self._load()
        return [h.path for h in self._hits]

    def getFactory(self):
        return PageFactory(self.source, self.rel_path,
                           copy.deepcopy(self.metadata))

    @property
    def _first_valid_hit(self):
        return self._hits[self._first_valid_hit_index]

    def _load(self):
        if self._hits is not None:
            return

        it = list(page_ref_pattern.finditer(self._page_ref))
        if len(it) == 0:
            raise Exception("Invalid page ref: %s" % self._page_ref)

        self._hits = []
        for m in it:
            source_name = m.group('src')
            source = self.app.getSource(source_name)
            if source is None:
                raise Exception("No such source: %s" % source_name)
            rel_path = m.group('path')
            if '%ext%' in rel_path:
                for e in self._exts:
                    cur_rel_path = rel_path.replace('%ext%', e)
                    path, metadata = source.resolveRef(cur_rel_path)
                    self._hits.append(self._HitInfo(
                            source_name, cur_rel_path, path, metadata))
            else:
                path, metadata = source.resolveRef(rel_path)
                self._hits.append(
                        self._HitInfo(source_name, rel_path, path, metadata))

    def _checkHits(self):
        if self._first_valid_hit_index >= 0:
            return
        if self._first_valid_hit_index == self._INDEX_NOT_FOUND:
            raise PageNotFoundError(
                    "No valid paths were found for page reference: %s" %
                    self._page_ref)

        self._load()
        self._first_valid_hit_index = self._INDEX_NOT_FOUND
        for i, hit in enumerate(self._hits):
            if os.path.isfile(hit.path):
                self._first_valid_hit_index = i
                break

