import logging
import collections
from piecrust.data.base import PaginationData, IPaginationSource
from piecrust.data.iterators import PageIterator
from piecrust.sources.base import IListableSource, build_pages


logger = logging.getLogger(__name__)


class LinkedPageData(PaginationData):
    debug_render = ['name', 'is_dir', 'is_self']

    def __init__(self, name, page, is_self=False):
        super(LinkedPageData, self).__init__(page)
        self.name = name
        self.is_self = is_self

    @property
    def is_dir(self):
        return False


class LinkerSource(IPaginationSource):
    def __init__(self, pages):
        self._pages = pages

    def getItemsPerPage(self):
        raise NotImplementedError()

    def getSourceIterator(self):
        return self._pages

    def getSorterIterator(self, it):
        return None

    def getTailIterator(self, it):
        return None

    def getPaginationFilter(self, page):
        return None

    def getSettingAccessor(self):
        return lambda i, n: i.get(n)


class LinkedPageDataIterator(object):
    def __init__(self, items):
        self._items = list(items)
        self._index = -1

    def __iter__(self):
        return self

    def __next__(self):
        self._index += 1
        if self._index >= len(self._items):
            raise StopIteration()
        return self._items[self._index]

    def sort(self, name):
        def key_getter(item):
            return item[name]
        self._items = sorted(self._item, key=key_getter)
        return self


class Linker(object):
    debug_render_doc = """Provides access to sibling and children pages."""

    def __init__(self, source, *, name=None, dir_path=None, page_path=None):
        self.source = source
        self._name = name
        self._dir_path = dir_path
        self._root_page_path = page_path
        self._cache = None
        self._is_listable = None

    def __iter__(self):
        self._load()
        return LinkedPageDataIterator(self._cache.values())

    def __getattr__(self, name):
        self._load()
        try:
            return self._cache[name]
        except KeyError:
            raise AttributeError()

    @property
    def name(self):
        if not self._name:
            self._load()
        return self._name

    @property
    def is_dir(self):
        return True

    @property
    def is_self(self):
        return False

    def _load(self):
        if self._cache is not None:
            return

        self._is_listable = isinstance(self.source, IListableSource)
        if self._is_listable and self._root_page_path is not None:
            if self._name is None:
                self._name = self.source.getBasename(self._root_page_path)
            if self._dir_path is None:
                self._dir_path = self.source.getDirpath(self._root_page_path)

        self._cache = collections.OrderedDict()
        if not self._is_listable or self._dir_path is None:
            return

        items = self.source.listPath(self._dir_path)
        with self.source.app.env.page_repository.startBatchGet():
            for is_dir, name, data in items:
                if is_dir:
                    self._cache[name] = Linker(self.source,
                                               name=name, dir_path=data)
                else:
                    page = data.buildPage()
                    is_root_page = (self._root_page_path == data.rel_path)
                    self._cache[name] = LinkedPageData(name, page,
                                                       is_root_page)


class RecursiveLinker(Linker):
    def __init__(self, source, *args, **kwargs):
        super(RecursiveLinker, self).__init__(source, *args, **kwargs)

    def __iter__(self):
        return iter(self.pages)

    def __getattr__(self, name):
        if name == 'pages':
            return self.getpages()
        if name == 'siblings':
            return self.getsiblings()
        raise AttributeError()

    def getpages(self):
        src = LinkerSource(self._iterateLinkers())
        return PageIterator(src)

    def getsiblings(self):
        src = LinkerSource(self._iterateLinkers(0))
        return PageIterator(src)

    def frompath(self, rel_path):
        return RecursiveLinker(self.source, name='.', dir_path=rel_path)

    def _iterateLinkers(self, max_depth=-1):
        self._load()
        if not self._is_listable:
            return
        yield from walk_linkers(self, 0, max_depth)


def walk_linkers(linker, depth=0, max_depth=-1):
    linker._load()
    for item in linker._cache.values():
        if item.is_dir:
            if max_depth < 0 or depth + 1 <= max_depth:
                yield from walk_linkers(item, depth + 1, max_depth)
        else:
            yield item

