import logging
from piecrust.data.filters import PaginationFilter
from piecrust.data.paginationdata import PaginationData
from piecrust.events import Event
from piecrust.dataproviders.base import DataProvider
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


class _ItInfo:
    def __init__(self):
        self.it = None
        self.iterated = False


class PageIteratorDataProvider(DataProvider):
    """ A data provider that reads a content source as a list of pages.

        This class supports wrapping another `PageIteratorDataProvider`
        instance because several sources may want to be merged under the
        same data endpoint (e.g. `site.pages` which lists both the user
        pages and the theme pages).
    """
    PROVIDER_NAME = 'page_iterator'

    debug_render_doc_dynamic = ['_debugRenderDoc']
    debug_render_not_empty = True

    def __init__(self, source, page):
        super().__init__(source, page)
        self._its = None
        self._app = source.app

    def __len__(self):
        self._load()
        return sum([len(i.it) for i in self._its])

    def __iter__(self):
        self._load()
        for i in self._its:
            yield from i.it

    def _load(self):
        if self._its is not None:
            return

        self._its = []
        for source in self._sources:
            i = _ItInfo()
            i.it = PageIterator(source, current_page=self._page)
            i.it._iter_event += self._onIteration
            self._its.append(i)

    def _onIteration(self, it):
        ii = next(filter(lambda i: i.it == it, self._its))
        if not ii.iterated:
            rcs = self._app.env.render_ctx_stack
            rcs.current_ctx.addUsedSource(self._source.name)
            ii.iterated = True

    def _debugRenderDoc(self):
        return 'Provides a list of %d items' % len(self)


class PageIterator:
    def __init__(self, source, *, current_page=None):
        self._source = source
        self._cache = None
        self._pagination_slicer = None
        self._has_sorter = False
        self._next_page = None
        self._prev_page = None
        self._locked = False
        self._iter_event = Event()
        self._current_page = current_page
        self._it = PageContentSourceIterator(self._source)

    @property
    def total_count(self):
        self._load()
        if self._pagination_slicer is not None:
            return self._pagination_slicer.inner_count
        return len(self._cache)

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
        return len(self._cache)

    def __getitem__(self, key):
        self._load()
        return self._cache[key]

    def __iter__(self):
        self._load()
        return iter(self._cache)

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
        if not setting_name:
            raise Exception("You need to specify a configuration setting "
                            "to sort by.")
        self._ensureUnlocked()
        self._ensureUnloaded()
        self._pages = SettingSortIterator(self._pages, setting_name, reverse)
        self._has_sorter = True
        return self

    def reset(self):
        self._ensureUnlocked()
        self._unload()
        return self

    @property
    def _is_loaded(self):
        return self._cache is not None

    @property
    def _has_more(self):
        if self._cache is None:
            return False
        if self._pagination_slicer:
            return self._pagination_slicer.has_more
        return False

    def _simpleWrap(self, it_class, *args, **kwargs):
        self._ensureUnlocked()
        self._ensureUnloaded()
        self._ensureSorter()
        self._it = it_class(self._it, *args, **kwargs)
        if self._pagination_slicer is None and it_class is SliceIterator:
            self._pagination_slicer = self._it
            self._pagination_slicer.current_page = self._current_page
        return self

    def _simpleNonSortedWrap(self, it_class, *args, **kwargs):
        self._ensureUnlocked()
        self._ensureUnloaded()
        self._it = it_class(self._it, *args, **kwargs)
        return self

    def _wrapAsSort(self, sort_it_class, *args, **kwargs):
        self._ensureUnlocked()
        self._ensureUnloaded()
        self._it = sort_it_class(self._it, *args, **kwargs)
        self._has_sorter = True
        return self

    def _lockIterator(self):
        self._ensureUnlocked()
        self._locked = True

    def _ensureUnlocked(self):
        if self._locked:
            raise Exception(
                "This page iterator has been locked and can't be modified.")

    def _ensureUnloaded(self):
        if self._cache:
            raise Exception(
                "This page iterator has already been iterated upon and "
                "can't be modified anymore.")

    def _ensureSorter(self):
        if self._has_sorter:
            return
        self._it = DateSortIterator(self._it, reverse=True)
        self._has_sorter = True

    def _unload(self):
        self._it = PageContentSourceIterator(self._source)
        self._cache = None
        self._paginationSlicer = None
        self._has_sorter = False
        self._next_page = None
        self._prev_page = None

    def _load(self):
        if self._cache is not None:
            return

        if self._source.app.env.abort_source_use:
            if self._current_page is not None:
                logger.debug("Aborting iteration of '%s' from: %s." %
                             (self._source.name,
                              self._current_page.content_spec))
            else:
                logger.debug("Aborting iteration of '%s'." %
                             self._source.name)
            raise AbortedSourceUseError()

        self._ensureSorter()

        tail_it = PaginationDataBuilderIterator(self._it, self._source.route)
        self._cache = list(tail_it)

        if (self._current_page is not None and
                self._pagination_slicer is not None):
            pn = [self._pagination_slicer.prev_page,
                  self._pagination_slicer.next_page]
            pn_it = PaginationDataBuilderIterator(iter(pn),
                                                  self._source.route)
            self._prev_page, self._next_page = (list(pn_it))

        self._iter_event.fire(self)

    def _debugRenderDoc(self):
        return "Contains %d items" % len(self)


class SettingFilterIterator:
    def __init__(self, it, fil_conf):
        self.it = it
        self.fil_conf = fil_conf
        self._fil = None

    def __iter__(self):
        if self._fil is None:
            self._fil = PaginationFilter()
            self._fil.addClausesFromConfig(self.fil_conf)

        for i in self.it:
            if self._fil.pageMatches(i):
                yield i


class HardCodedFilterIterator:
    def __init__(self, it, fil):
        self.it = it
        self._fil = fil

    def __iter__(self):
        for i in self.it:
            if self._fil.pageMatches(i):
                yield i


class SliceIterator:
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

            if self.limit > 0:
                self.has_more = self.inner_count > (self.offset + self.limit)
                self._cache = inner_list[self.offset:self.offset + self.limit]
            else:
                self.has_more = False
                self._cache = inner_list[self.offset:]

            if self.current_page:
                try:
                    idx = inner_list.index(self.current_page)
                except ValueError:
                    idx = -1
                if idx >= 0:
                    if idx < self.inner_count - 1:
                        self.next_page = inner_list[idx + 1]
                    if idx > 0:
                        self.prev_page = inner_list[idx - 1]

        return iter(self._cache)


class SettingSortIterator:
    def __init__(self, it, name, reverse=False):
        self.it = it
        self.name = name
        self.reverse = reverse

    def __iter__(self):
        return iter(sorted(self.it, key=self._key_getter,
                           reverse=self.reverse))

    def _key_getter(self, item):
        key = item.config.get(item)
        if key is None:
            return 0
        return key


class DateSortIterator:
    def __init__(self, it, reverse=True):
        self.it = it
        self.reverse = reverse

    def __iter__(self):
        return iter(sorted(self.it,
                           key=lambda x: x.datetime, reverse=self.reverse))


class PageContentSourceIterator:
    def __init__(self, source):
        self.source = source

        # This is to permit recursive traversal of the
        # iterator chain. It acts as the end.
        self.it = None

    def __iter__(self):
        source = self.source
        app = source.app
        for item in source.getAllContents():
            yield app.getPage(source, item)


class PaginationDataBuilderIterator:
    def __init__(self, it, route):
        self.it = it
        self.route = route

    def __iter__(self):
        for page in self.it:
            if page is not None:
                yield PaginationData(page)
            else:
                yield None

