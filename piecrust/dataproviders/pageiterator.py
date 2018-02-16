import logging
from piecrust.data.filters import PaginationFilter
from piecrust.data.paginationdata import PaginationData
from piecrust.events import Event
from piecrust.dataproviders.base import DataProvider
from piecrust.sources.base import ContentSource


logger = logging.getLogger(__name__)


class _CombinedSource:
    def __init__(self, sources):
        self.sources = sources
        self.app = sources[0].app
        self.name = None

        # This is for recursive traversal of the iterator chain.
        # See later in `PageIterator`.
        self.it = None

    def __iter__(self):
        sources = self.sources

        if len(sources) == 1:
            source = sources[0]
            self.name = source.name
            yield from source.getAllPages()
            self.name = None
            return

        # Return the pages from all the combined sources, but skip
        # those that are "overridden" -- e.g. a theme page that gets
        # replaced by a user page of the same name.
        used_uris = set()
        for source in sources:
            self.name = source.name
            for page in source.getAllPages():
                page_uri = page.getUri()
                if page_uri not in used_uris:
                    used_uris.add(page_uri)
                    yield page

        self.name = None


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
        self._app = source.app
        self._it = None
        self._iterated = False

    def __len__(self):
        self._load()
        return len(self._it)

    def __iter__(self):
        self._load()
        yield from self._it

    def _load(self):
        if self._it is not None:
            return

        combined_source = _CombinedSource(list(reversed(self._sources)))
        self._it = PageIterator(combined_source, current_page=self._page)
        self._it._load_event += self._onIteration

    def _onIteration(self, it):
        if not self._iterated:
            rcs = self._app.env.render_ctx_stack
            if rcs.current_ctx is not None:
                rcs.current_ctx.addUsedSource(it._source)
            self._iterated = True

    def _addSource(self, source):
        if self._it is not None:
            raise Exception("Can't add sources after the data provider "
                            "has been loaded.")
        super()._addSource(source)

    def _debugRenderDoc(self):
        return 'Provides a list of %d items' % len(self)


class PageIterator:
    def __init__(self, source, *, current_page=None):
        self._source = source
        self._is_content_source = isinstance(
            source, (ContentSource, _CombinedSource))
        self._cache = None
        self._pagination_slicer = None
        self._has_sorter = False
        self._next_page = None
        self._prev_page = None
        self._locked = False
        self._load_event = Event()
        self._iter_event = Event()
        self._current_page = current_page
        self._initIterator()

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
        self._iter_event.fire(self)
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

    def sort(self, setting_name=None, reverse=False):
        if setting_name:
            self._wrapAsSort(SettingSortIterator, setting_name, reverse)
        else:
            self._wrapAsSort(NaturalSortIterator, reverse)
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
        self._load()
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
        if self._is_content_source:
            # For content sources, the default sorting is reverse
            # date/time sorting.
            self._it = DateSortIterator(self._it, reverse=True)
        self._has_sorter = True

    def _initIterator(self):
        if self._is_content_source:
            if isinstance(self._source, _CombinedSource):
                self._it = self._source
            else:
                self._it = PageContentSourceIterator(self._source)

            app = self._source.app
            if app.config.get('baker/is_baking'):
                # While baking, automatically exclude any page with
                # the `draft` setting.
                draft_setting = app.config['baker/no_bake_setting']
                self._it = NoDraftsIterator(self._it, draft_setting)
        else:
            self._it = GenericSourceIterator(self._source)

    def _unload(self):
        self._initIterator()
        self._cache = None
        self._paginationSlicer = None
        self._has_sorter = False
        self._next_page = None
        self._prev_page = None

    def _load(self):
        if self._cache is not None:
            return

        self._ensureSorter()

        if self._is_content_source:
            self._it = PaginationDataBuilderIterator(self._it)

        self._cache = list(self._it)

        if (self._current_page is not None and
                self._pagination_slicer is not None):
            pn = [self._pagination_slicer.prev_page,
                  self._pagination_slicer.next_page]
            pn_it = PaginationDataBuilderIterator(iter(pn))
            self._prev_page, self._next_page = (list(pn_it))

        self._load_event.fire(self)

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


class NaturalSortIterator:
    def __init__(self, it, reverse=False):
        self.it = it
        self.reverse = reverse

    def __iter__(self):
        return iter(sorted(self.it, reverse=self.reverse))


class SettingSortIterator:
    def __init__(self, it, name, reverse=False):
        self.it = it
        self.name = name
        self.reverse = reverse

    def __iter__(self):
        return iter(sorted(self.it, key=self._key_getter,
                           reverse=self.reverse))

    def _key_getter(self, item):
        key = item.config.get(self.name)
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
        yield from source.getAllPages()


class NoDraftsIterator:
    def __init__(self, source, no_draft_setting):
        self.it = source
        self.no_draft_setting = no_draft_setting

    def __iter__(self):
        nds = self.no_draft_setting
        yield from filter(lambda i: not i.config.get(nds), self.it)


class PaginationDataBuilderIterator:
    def __init__(self, it):
        self.it = it

    def __iter__(self):
        for page in self.it:
            if page is not None:
                yield PaginationData(page)
            else:
                yield None


class GenericSourceIterator:
    def __init__(self, source):
        self.source = source
        self.it = None

    def __iter__(self):
        yield from self.source
