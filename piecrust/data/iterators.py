import logging
from piecrust.data.base import IPaginationSource
from piecrust.data.filters import PaginationFilter
from piecrust.events import Event


logger = logging.getLogger(__name__)


class SliceIterator(object):
    def __init__(self, it, offset=0, limit=-1):
        self.it = it
        self.offset = offset
        self.limit = limit
        self.current_page = None
        self.has_more = False
        self.inner_count = -1
        self.next_page = None
        self.prev_page = None
        self._cache = None

    def __iter__(self):
        if self._cache is None:
            inner_list = list(self.it)
            self.inner_count = len(inner_list)
            self.has_more = self.inner_count > (self.offset + self.limit)
            self._cache = inner_list[self.offset:self.offset + self.limit]
            if self.current_page:
                idx = inner_list.index(self.current_page)
                if idx >= 0:
                    if idx < self.inner_count - 1:
                        self.next_page = inner_list[idx + 1]
                    if idx > 0:
                        self.prev_page = inner_list[idx - 1]
        return iter(self._cache)


class SettingFilterIterator(object):
    def __init__(self, it, fil_conf, page_accessor=None):
        self.it = it
        self.fil_conf = fil_conf
        self._fil = None
        self.page_accessor = page_accessor

    def __iter__(self):
        if self._fil is None:
            self._fil = PaginationFilter()
            self._fil.addClausesFromConfig(self.fil_conf)

        for i in self.it:
            if self.page_accessor:
                page = self.page_accessor(i)
            else:
                page = i
            if self._fil.pageMatches(page):
                yield i


class SettingSortIterator(object):
    def __init__(self, it, name, reverse=False, value_accessor=None):
        self.it = it
        self.name = name
        self.reverse = reverse
        self.value_accessor = value_accessor

    def __iter__(self):
        def comparer(x, y):
            if self.value_accessor:
                v1 = self.value_accessor(x, self.name)
                v2 = self.value_accessor(y, self.name)
            else:
                v1 = x.config.get(self.name)
                v2 = y.config.get(self.name)

            if v1 is None and v2 is None:
                return 0
            if v1 is None and v2 is not None:
                return 1 if self.reverse else -1
            if v1 is not None and v2 is None:
                return -1 if self.reverse else 1

            if v1 == v2:
                return 0
            if self.reverse:
                return 1 if v1 < v2 else -1
            else:
                return -1 if v1 < v2 else 1

        return sorted(self.it, cmp=self._comparer, reverse=self.reverse)


class PaginationFilterIterator(object):
    def __init__(self, it, fil):
        self.it = it
        self._fil = fil

    def __iter__(self):
        for page in self.it:
            if self._fil.pageMatches(page):
                yield page


class PageIterator(object):
    def __init__(self, source, current_page=None, pagination_filter=None,
            offset=0, limit=-1, locked=False):
        self._source = source
        self._current_page = current_page
        self._locked = False
        self._pages = source
        self._pagesData = None
        self._pagination_slicer = None
        self._has_sorter = False
        self._next_page = None
        self._prev_page = None
        self._iter_event = Event()

        if isinstance(source, IPaginationSource):
            src_it = source.getSourceIterator()
            if src_it is not None:
                self._pages = src_it

        # Apply any filter first, before we start sorting or slicing.
        if pagination_filter is not None:
            self._simpleNonSortedWrap(PaginationFilterIterator,
                    pagination_filter)

        if offset > 0 or limit > 0:
            self.slice(offset, limit)

        self._locked = locked

    @property
    def total_count(self):
        self._load()
        if self._pagination_slicer is not None:
            return self._pagination_slicer.inner_count
        return len(self._pagesData)

    @property
    def next_page(self):
        self._load()
        return self._next_page

    @property
    def prev_page(self):
        self._load()
        return self._prev_page

    def __len__(self):
        self._load()
        return len(self._pagesData)

    def __getitem__(self, key):
        self._load()
        return self._pagesData[key]

    def __iter__(self):
        self._load()
        self._iter_event.fire()
        return iter(self._pagesData)

    def __getattr__(self, name):
        if name[:3] == 'is_' or name[:3] == 'in_':
            def is_filter(value):
                conf = {'is_%s' % name[3:]: value}
                return self._simpleNonSortedWrap(SettingFilterIterator, conf)
            return is_filter

        if name[:4] == 'has_':
            def has_filter(value):
                conf = {name: value}
                return self._simpleNonSortedWrap(SettingFilterIterator, conf)
            return has_filter

        if name[:5] == 'with_':
            def has_filter(value):
                conf = {'has_%s' % name[5:]: value}
                return self._simpleNonSortedWrap(SettingFilterIterator, conf)
            return has_filter

        return self.__getattribute__(name)

    def skip(self, count):
        return self._simpleWrap(SliceIterator, count)

    def limit(self, count):
        return self._simpleWrap(SliceIterator, 0, count)

    def slice(self, skip, limit):
        return self._simpleWrap(SliceIterator, skip, limit)

    def filter(self, filter_name):
        if self._current_page is None:
            raise Exception("Can't use `filter()` because no parent page was "
                            "set for this page iterator.")
        filter_conf = self._current_page.config.get(filter_name)
        if filter_conf is None:
            raise Exception("Couldn't find filter '%s' in the configuration "
                            "header for page: %s" %
                            (filter_name, self._current_page.path))
        return self._simpleNonSortedWrap(SettingFilterIterator, filter_conf)

    def sort(self, setting_name, reverse=False):
        self._ensureUnlocked()
        self._unload()
        self._pages = SettingSortIterator(self._pages, setting_name, reverse)
        self._has_sorter = True
        return self

    def reset(self):
        self._ensureUnlocked()
        self._unload
        return self

    @property
    def _has_more(self):
        self._load()
        if self._pagination_slicer:
            return self._pagination_slicer.has_more
        return False

    def _simpleWrap(self, it_class, *args, **kwargs):
        self._ensureUnlocked()
        self._unload()
        self._ensureSorter()
        self._pages = it_class(self._pages, *args, **kwargs)
        if self._pagination_slicer is None and it_class is SliceIterator:
            self._pagination_slicer = self._pages
        return self

    def _simpleNonSortedWrap(self, it_class, *args, **kwargs):
        self._ensureUnlocked()
        self._unload()
        self._pages = it_class(self._pages, *args, **kwargs)
        return self

    def _ensureUnlocked(self):
        if self._locked:
            raise Exception(
                    "This page iterator has been locked, probably because "
                    "you're trying to tamper with pagination data.")

    def _ensureSorter(self):
        if self._has_sorter:
            return
        if isinstance(self._source, IPaginationSource):
            sort_it = self._source.getSorterIterator(self._pages)
            if sort_it is not None:
                self._pages = sort_it
        self._has_sorter = True

    def _unload(self):
        self._pagesData = None
        self._next_page = None
        self._prev_page = None

    def _load(self):
        if self._pagesData is not None:
            return

        self._ensureSorter()

        it_chain = self._pages
        is_pgn_source = False
        if isinstance(self._source, IPaginationSource):
            is_pgn_source = True
            tail_it = self._source.getTailIterator(self._pages)
            if tail_it is not None:
                it_chain = tail_it

        self._pagesData = list(it_chain)

        if is_pgn_source and self._current_page and self._pagination_slicer:
            pn = [self._pagination_slicer.prev_page,
                    self._pagination_slicer.next_page]
            pn_it = self._source.getTailIterator(iter(pn))
            self._prev_page, self._next_page = (list(pn_it))

