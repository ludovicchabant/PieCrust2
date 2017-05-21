import logging
import collections
from piecrust.data.pagedata import LazyPageConfigLoaderHasNoValue
from piecrust.data.paginationdata import PaginationData
from piecrust.dataproviders.page_iterator import PageIterator


logger = logging.getLogger(__name__)


class PageLinkerData(object):
    """ Entry template data to get access to related pages from a given
        root page.
    """
    debug_render = ['parent', 'ancestors', 'siblings', 'children', 'root',
                    'forpath']
    debug_render_invoke = ['parent', 'ancestors', 'siblings', 'children',
                           'root']
    debug_render_redirect = {
        'ancestors': '_debugRenderAncestors',
        'siblings': '_debugRenderSiblings',
        'children': '_debugRenderChildren',
        'root': '_debugRenderRoot'}

    def __init__(self, source, page_path):
        self._source = source
        self._root_page_path = page_path
        self._linker = None
        self._is_loaded = False

    @property
    def parent(self):
        self._load()
        if self._linker is not None:
            return self._linker.parent
        return None

    @property
    def ancestors(self):
        cur = self.parent
        while cur:
            yield cur
            cur = cur.parent

    @property
    def siblings(self):
        self._load()
        if self._linker is None:
            return []
        return self._linker

    @property
    def children(self):
        self._load()
        if self._linker is None:
            return []
        self._linker._load()
        if self._linker._self_item is None:
            return []
        children = self._linker._self_item._linker_info.child_linker
        if children is None:
            return []
        return children

    @property
    def root(self):
        self._load()
        if self._linker is None:
            return None
        return self._linker.root

    def forpath(self, rel_path):
        self._load()
        if self._linker is None:
            return None
        return self._linker.forpath(rel_path)

    def _load(self):
        if self._is_loaded:
            return

        self._is_loaded = True

        dir_path = self._source.getDirpath(self._root_page_path)
        self._linker = Linker(self._source, dir_path,
                              root_page_path=self._root_page_path)

    def _debugRenderAncestors(self):
        return [i.name for i in self.ancestors]

    def _debugRenderSiblings(self):
        return [i.name for i in self.siblings]

    def _debugRenderChildren(self):
        return [i.name for i in self.children]

    def _debugRenderRoot(self):
        r = self.root
        if r is not None:
            return r.name
        return None


class LinkedPageData(PaginationData):
    """ Class whose instances get returned when iterating on a `Linker`
        or `RecursiveLinker`. It's just like what gets usually returned by
        `Paginator` and other page iterators, but with a few additional data
        like hierarchical data.
    """
    debug_render = (['is_dir', 'is_self', 'parent', 'children'] +
                    PaginationData.debug_render)
    debug_render_invoke = (['is_dir', 'is_self', 'parent', 'children'] +
                           PaginationData.debug_render_invoke)

    def __init__(self, page):
        super(LinkedPageData, self).__init__(page)
        self.name = page._linker_info.name
        self.is_self = page._linker_info.is_self
        self.is_dir = page._linker_info.is_dir
        self.is_page = True
        self._child_linker = page._linker_info.child_linker

        self._mapLoader('*', self._linkerChildLoader)

    @property
    def parent(self):
        if self._child_linker is not None:
            return self._child_linker.parent
        return None

    @property
    def children(self):
        if self._child_linker is not None:
            return self._child_linker
        return []

    def _linkerChildLoader(self, data, name):
        if self.children and hasattr(self.children, name):
            return getattr(self.children, name)
        raise LazyPageConfigLoaderHasNoValue


class LinkedPageDataBuilderIterator(object):
    """ Iterator that builds `LinkedPageData` out of pages.
    """
    def __init__(self, it):
        self.it = it

    def __iter__(self):
        for item in self.it:
            yield LinkedPageData(item)


class LinkerSource(IPaginationSource):
    """ Source iterator that returns pages given by `Linker`.
    """
    def __init__(self, pages, orig_source):
        self._pages = list(pages)
        self._orig_source = None
        if isinstance(orig_source, IPaginationSource):
            self._orig_source = orig_source

    def getItemsPerPage(self):
        raise NotImplementedError()

    def getSourceIterator(self):
        return self._pages

    def getSorterIterator(self, it):
        # We don't want to sort the pages -- we expect the original source
        # to return hierarchical items in the order it wants already.
        return None

    def getTailIterator(self, it):
        return LinkedPageDataBuilderIterator(it)

    def getPaginationFilter(self, page):
        return None

    def getSettingAccessor(self):
        if self._orig_source:
            return self._orig_source.getSettingAccessor()
        return None


class _LinkerInfo(object):
    def __init__(self):
        self.name = None
        self.is_dir = False
        self.is_self = False
        self.child_linker = None


class _LinkedPage(object):
    def __init__(self, page):
        self._page = page
        self._linker_info = _LinkerInfo()

    def __getattr__(self, name):
        return getattr(self._page, name)


class Linker(object):
    debug_render_doc = """Provides access to sibling and children pages."""

    def __init__(self, source, dir_path, *, root_page_path=None):
        self._source = source
        self._dir_path = dir_path
        self._root_page_path = root_page_path
        self._items = None
        self._parent = None
        self._self_item = None

        self.is_dir = True
        self.is_page = False
        self.is_self = False

    def __iter__(self):
        return iter(self.pages)

    def __getattr__(self, name):
        self._load()
        try:
            item = self._items[name]
        except KeyError:
            raise AttributeError()

        if isinstance(item, Linker):
            return item

        return LinkedPageData(item)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self._source.getBasename(self._dir_path)

    @property
    def children(self):
        return self._iterItems(0)

    @property
    def parent(self):
        if self._dir_path == '':
            return None

        if self._parent is None:
            parent_name = self._source.getBasename(self._dir_path)
            parent_dir_path = self._source.getDirpath(self._dir_path)
            for is_dir, name, data in self._source.listPath(parent_dir_path):
                if not is_dir and name == parent_name:
                    parent_page = data.buildPage()
                    item = _LinkedPage(parent_page)
                    item._linker_info.name = parent_name
                    item._linker_info.child_linker = Linker(
                        self._source, parent_dir_path,
                        root_page_path=self._root_page_path)
                    self._parent = LinkedPageData(item)
                    break
            else:
                self._parent = Linker(self._source, parent_dir_path,
                                      root_page_path=self._root_page_path)

        return self._parent

    @property
    def pages(self):
        return self._iterItems(0, filter_page_items)

    @property
    def directories(self):
        return self._iterItems(0, filter_directory_items)

    @property
    def all(self):
        return self._iterItems()

    @property
    def allpages(self):
        return self._iterItems(-1, filter_page_items)

    @property
    def alldirectories(self):
        return self._iterItems(-1, filter_directory_items)

    @property
    def root(self):
        return self.forpath('/')

    def forpath(self, rel_path):
        return Linker(self._source, rel_path,
                      root_page_path=self._root_page_path)

    def _iterItems(self, max_depth=-1, filter_func=None):
        items = walk_linkers(self, max_depth=max_depth,
                             filter_func=filter_func)
        src = LinkerSource(items, self._source)
        return PageIterator(src)

    def _load(self):
        if self._items is not None:
            return

        items = list(self._source.listPath(self._dir_path))
        self._items = collections.OrderedDict()
        for is_dir, name, data in items:
            # If `is_dir` is true, `data` will be the directory's source
            # path. If not, it will be a page factory.
            if is_dir:
                item = Linker(self._source, data,
                              root_page_path=self._root_page_path)
            else:
                page = data.buildPage()
                is_self = (page.rel_path == self._root_page_path)
                item = _LinkedPage(page)
                item._linker_info.name = name
                item._linker_info.is_self = is_self
                if is_self:
                    self._self_item = item

            existing = self._items.get(name)
            if existing is None:
                self._items[name] = item
            elif is_dir:
                # The current item is a directory. The existing item
                # should be a page.
                existing._linker_info.child_linker = item
                existing._linker_info.is_dir = True
            else:
                # The current item is a page. The existing item should
                # be a directory.
                item._linker_info.child_linker = existing
                item._linker_info.is_dir = True
                self._items[name] = item


def filter_page_items(item):
    return not isinstance(item, Linker)


def filter_directory_items(item):
    return isinstance(item, Linker)


def walk_linkers(linker, depth=0, max_depth=-1, filter_func=None):
    linker._load()
    for item in linker._items.values():
        if not filter_func or filter_func(item):
            yield item

        if (isinstance(item, Linker) and
                (max_depth < 0 or depth + 1 <= max_depth)):
            yield from walk_linkers(item, depth + 1, max_depth)

