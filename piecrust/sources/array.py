from piecrust.sources.base import PageSource
from piecrust.sources.mixins import SimplePaginationSourceMixin


class CachedPageFactory(object):
    """ A `PageFactory` (in appearance) that already has a page built.
    """
    def __init__(self, page):
        self._page = page

    @property
    def rel_path(self):
        return self._page.rel_path

    @property
    def metadata(self):
        return self._page.source_metadata

    @property
    def ref_spec(self):
        return self._page.ref_spec

    @property
    def path(self):
        return self._page.path

    def buildPage(self):
        return self._page


class ArraySource(PageSource, SimplePaginationSourceMixin):
    def __init__(self, app, inner_source, name='array', config=None):
        super(ArraySource, self).__init__(app, name, config or {})
        self.inner_source = inner_source

    @property
    def page_count(self):
        return len(self.inner_source)

    def getPageFactories(self):
        for p in self.inner_source:
            yield CachedPageFactory(p)

