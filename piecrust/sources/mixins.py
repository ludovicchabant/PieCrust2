import os.path
import logging
from piecrust import osutil
from piecrust.data.paginationdata import PaginationData
from piecrust.sources.base import ContentItem
from piecrust.sources.interfaces import IPaginationSource


logger = logging.getLogger(__name__)

assets_suffix = '-assets'


class ContentSourceIterator(object):
    def __init__(self, source):
        self.source = source

        # This is to permit recursive traversal of the
        # iterator chain. It acts as the end.
        self.it = None

    def __iter__(self):
        return self.source.getAllContentItems()


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
            if page is not None:
                yield PaginationData(page)
            else:
                yield None


class SimplePaginationSourceMixin(IPaginationSource):
    """ Implements the `IPaginationSource` interface in a standard way that
        should fit most page sources.
    """
    def getItemsPerPage(self):
        return self.config['items_per_page']

    def getSourceIterator(self):
        return ContentSourceIterator(self)

    def getSorterIterator(self, it):
        return DateSortIterator(it)

    def getTailIterator(self, it):
        return PaginationDataBuilderIterator(it)


class SimpleAssetsSubDirMixin:
    def _getRelatedAssetsContents(self, item, relationship):
        if not item.metadata.get('__has_assets', False):
            return None

        assets = {}
        assets_dir = item.spec + assets_suffix
        for f in osutil.listdir(assets_dir):
            fpath = os.path.join(assets_dir, f)
            name, _ = os.path.splitext(f)
            if name in assets:
                raise Exception("Multiple assets are named '%s'." %
                                name)
            assets[name] = ContentItem(fpath, {'__is_asset': True})
        return assets

    def _onFinalizeContent(self, parent_group, items, groups):
        assetsGroups = []
        for g in groups:
            if not g.spec.endswith(assets_suffix):
                continue
            match = g.spec[:-len(assets_suffix)]
            item = next(filter(lambda i: i.spec == match), None)
            if item:
                item.metadata['__has_assets'] = True
                assetsGroups.append(g)
        for g in assetsGroups:
            groups.remove(g)

