import logging
import collections
from piecrust.data.base import PaginationData
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
        return iter(self._cache.values())

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
    def __init__(self, source, page_path):
        super(RecursiveLinker, self).__init__(source, page_path=page_path)

    def __iter__(self):
        self._load()
        if not self._is_listable:
            return
        yield from walk_linkers(self)


def walk_linkers(linker):
    linker._load()
    for item in linker._cache.values():
        if item.is_dir:
            yield from walk_linkers(item)
        else:
            yield item

