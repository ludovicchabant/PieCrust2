import logging
import collections
from piecrust.data.base import PaginationData
from piecrust.data.iterators import PageIterator
from piecrust.sources.base import build_pages
from piecrust.sources.interfaces import IPaginationSource, IListableSource


logger = logging.getLogger(__name__)


class PageLinkerData(object):
    """ Entry template data to get access to related pages from a given
        root page.
    """
    def __init__(self, source, page_path):
        self._linker = Linker(source, page_path)

    @property
    def siblings(self):
        return self._linker

    @property
    def children(self):
        self._linker._load()
        if self._linker._self_item is None:
            return None
        return self._linker._self_item._linker_info.child_linker

    @property
    def root(self):
        return self._linker.root

    def forpath(self, rel_path):
        return self._linker.forpath(rel_path)


class LinkedPageData(PaginationData):
    """ Class whose instances get returned when iterating on a `Linker`
        or `RecursiveLinker`. It's just like what gets usually returned by
        `Paginator` and other page iterators, but with a few additional data
        like hierarchical data.
    """
    debug_render = ['is_dir', 'is_self'] + PaginationData.debug_render

    def __init__(self, page):
        super(LinkedPageData, self).__init__(page)
        self.name = page._linker_info.name
        self.is_self = page._linker_info.is_self
        self.children = page._linker_info.child_linker
        self.is_dir = (self.children is not None)
        self.is_page = True

        self.mapLoader('*', self._linkerChildLoader)

    def _linkerChildLoader(self, name):
        return getattr(self.children, name)


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

    def __init__(self, source, root_page_path, *, name=None, dir_path=None):
        self._source = source
        self._root_page_path = root_page_path
        self._name = name
        self._dir_path = dir_path
        self._items = None
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

    @property
    def name(self):
        if self._name is None:
            self._load()
        return self._name

    @property
    def children(self):
        return self._iterItems(0)

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
        return Linker(self._source, self._root_page_path,
                      name='.', dir_path=rel_path)

    def _iterItems(self, max_depth=-1, filter_func=None):
        items = walk_linkers(self, max_depth=max_depth,
                             filter_func=filter_func)
        src = LinkerSource(items, self._source)
        return PageIterator(src)

    def _load(self):
        if self._items is not None:
            return

        is_listable = isinstance(self._source, IListableSource)
        if not is_listable:
            raise Exception("Source '%s' can't be listed." % self._source.name)

        if self._name is None:
            self._name = self._source.getBasename(self._root_page_path)
        if self._dir_path is None:
            self._dir_path = self._source.getDirpath(self._root_page_path)

        if self._dir_path is None:
            raise Exception("This linker has no directory to start from.")

        items = list(self._source.listPath(self._dir_path))
        self._items = collections.OrderedDict()
        with self._source.app.env.page_repository.startBatchGet():
            for is_dir, name, data in items:
                # If `is_dir` is true, `data` will be the directory's source
                # path. If not, it will be a page factory.
                if is_dir:
                    item = Linker(self._source, self._root_page_path,
                                  name=name, dir_path=data)
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
                else:
                    # The current item is a page. The existing item should
                    # be a directory.
                    item._linker_info.child_linker = existing
                    self._items[name] = item


def filter_page_items(item):
    return not isinstance(item, Linker)


def filter_directory_items(item):
    return isinstance(item, linker)


def walk_linkers(linker, depth=0, max_depth=-1, filter_func=None):
    linker._load()
    for item in linker._items.values():
        if not filter_func or filter_func(item):
            yield item

        if (isinstance(item, Linker) and
                (max_depth < 0 or depth + 1 <= max_depth)):
            yield from walk_linkers(item, depth + 1, max_depth)

