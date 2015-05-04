import os
import os.path
import logging
from piecrust.data.base import PaginationData
from piecrust.data.filters import PaginationFilter, page_value_accessor
from piecrust.sources.base import PageFactory
from piecrust.sources.interfaces import IPaginationSource, IListableSource
from piecrust.sources.pageref import PageNotFoundError


logger = logging.getLogger(__name__)


class SourceFactoryIterator(object):
    def __init__(self, source):
        self.source = source

        # This is to permit recursive traversal of the
        # iterator chain. It acts as the end.
        self.it = None

    def __iter__(self):
        return self.source.getPages()


class SourceFactoryWithoutTaxonomiesIterator(object):
    def __init__(self, source):
        self.source = source
        self._taxonomy_pages = None
        # See comment above.
        self.it = None

    def __iter__(self):
        self._cacheTaxonomyPages()
        for p in self.source.getPages():
            if p.rel_path in self._taxonomy_pages:
                continue
            yield p

    def _cacheTaxonomyPages(self):
        if self._taxonomy_pages is not None:
            return

        self._taxonomy_pages = set()
        for tax in self.source.app.taxonomies:
            page_ref = tax.getPageRef(self.source.name)
            try:
                self._taxonomy_pages.add(page_ref.rel_path)
            except PageNotFoundError:
                pass


class DateSortIterator(object):
    def __init__(self, it, reverse=True):
        self.it = it
        self.reverse = reverse

    def __iter__(self):
        return iter(sorted(self.it,
                           key=lambda x: x.datetime, reverse=self.reverse))


class PaginationDataBuilderIterator(object):
    def __init__(self, it):
        self.it = it

    def __iter__(self):
        for page in self.it:
            if page is None:
                yield None
            else:
                yield PaginationData(page)


class SimplePaginationSourceMixin(IPaginationSource):
    """ Implements the `IPaginationSource` interface in a standard way that
        should fit most page sources.
    """
    def getItemsPerPage(self):
        return self.config['items_per_page']

    def getSourceIterator(self):
        if self.config.get('iteration_includes_taxonomies', False):
            return SourceFactoryIterator(self)
        return SourceFactoryWithoutTaxonomiesIterator(self)

    def getSorterIterator(self, it):
        return DateSortIterator(it)

    def getTailIterator(self, it):
        return PaginationDataBuilderIterator(it)

    def getPaginationFilter(self, page):
        conf = (page.config.get('items_filters') or
                self.config.get('items_filters'))
        if conf == 'none' or conf == 'nil' or conf == '':
            conf = None
        if conf is not None:
            f = PaginationFilter(value_accessor=page_value_accessor)
            f.addClausesFromConfig(conf)
            return f
        return None

    def getSettingAccessor(self):
        return page_value_accessor


class SimpleListableSourceMixin(IListableSource):
    """ Implements the `IListableSource` interface for sources that map to
        simple file-system structures.
    """
    def listPath(self, rel_path):
        rel_path = rel_path.lstrip('\\/')
        path = self._getFullPath(rel_path)
        names = self._sortFilenames(os.listdir(path))

        items = []
        for name in names:
            if os.path.isdir(os.path.join(path, name)):
                if self._filterPageDirname(name):
                    rel_subdir = os.path.join(rel_path, name)
                    items.append((True, name, rel_subdir))
            else:
                if self._filterPageFilename(name):
                    slug = self._makeSlug(os.path.join(rel_path, name))
                    metadata = {'slug': slug}

                    fac_path = name
                    if rel_path != '.':
                        fac_path = os.path.join(rel_path, name)
                    fac_path = fac_path.replace('\\', '/')

                    self._populateMetadata(fac_path, metadata)
                    fac = PageFactory(self, fac_path, metadata)

                    name, _ = os.path.splitext(name)
                    items.append((False, name, fac))
        return items

    def getDirpath(self, rel_path):
        return os.path.dirname(rel_path)

    def getBasename(self, rel_path):
        filename = os.path.basename(rel_path)
        name, _ = os.path.splitext(filename)
        return name

    def _getFullPath(self, rel_path):
        return os.path.join(self.fs_endpoint_path, rel_path)

    def _sortFilenames(self, names):
        return sorted(names)

    def _filterPageDirname(self, name):
        return True

    def _filterPageFilename(self, name):
        return True

    def _makeSlug(self, rel_path):
        return rel_path.replace('\\', '/')

    def _populateMetadata(self, rel_path, metadata, mode=None):
        pass

