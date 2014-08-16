import time
import logging
from piecrust.data.assetor import Assetor


logger = logging.getLogger(__name__)


class IPaginationSource(object):
    def getItemsPerPage(self):
        raise NotImplementedError()

    def getSourceIterator(self):
        raise NotImplementedError()

    def getSorterIterator(self, it):
        raise NotImplementedError()

    def getTailIterator(self, it):
        raise NotImplementedError()

    def getPaginationFilter(self, page):
        raise NotImplementedError()


class LazyPageConfigData(object):
    """ An object that represents the configuration header of a page,
        but also allows for additional data. It's meant to be exposed
        to the templating system.
    """
    def __init__(self, page):
        self._page = page
        self._values = None
        self._loaders = None

    @property
    def page(self):
        return self._page

    def __getitem__(self, name):
        self._load()

        if self._loaders:
            loader = self._loaders.get(name)
            if loader is not None:
                try:
                    self._values[name] = loader(self, name)
                except Exception as ex:
                    logger.error("Error while loading attribute '%s' for: %s"
                            % (name, self._page.path))
                    logger.exception(ex)
                    raise Exception("Internal Error: %s" % ex)

                # We need to double-check `_loaders` here because
                # the loader could have removed all loaders, which
                # would set this back to `None`.
                if self._loaders is not None:
                    del self._loaders[name]
                    if len(self._loaders) == 0:
                        self._loaders = None

        return self._values[name]

    def setValue(self, name, value):
        self._values[name] = value

    def mapLoader(self, attr_name, loader):
        if loader is None:
            if self._loaders is None or attr_name not in self._loaders:
                return
            del self._loaders[attr_name]
            if len(self._loaders) == 0:
                self._loaders = None
            return

        if self._loaders is None:
            self._loaders = {}
        if attr_name in self._loaders:
            raise Exception("A loader has already been mapped for: %s" %
                    attr_name)
        self._loaders[attr_name] = loader

    def _load(self):
        if self._values is not None:
            return
        self._values = dict(self._page.config.get())
        try:
            self._loadCustom()
        except Exception as ex:
            logger.error("Error while loading data for: %s" % self._page.path)
            logger.exception(ex)
            raise Exception("Internal Error: %s" % ex)

    def _loadCustom(self):
        pass


class PaginationData(LazyPageConfigData):
    def __init__(self, page):
        super(PaginationData, self).__init__(page)

    def _get_uri(self):
        page = self._page
        route = page.app.getRoute(page.source.name, page.source_metadata)
        if route is None:
            raise Exception("Can't get route for page: %s" % page.path)
        return route.getUri(page.source_metadata)

    def _loadCustom(self):
        page_url = self._get_uri()
        self.setValue('url', page_url)
        self.setValue('slug', page_url)
        self.setValue('timestamp',
                time.mktime(self.page.datetime.timetuple()))
        date_format = self.page.app.config.get('site/date_format')
        if date_format:
            self.setValue('date', self.page.datetime.strftime(date_format))

        assetor = Assetor(self.page, page_url)
        self.setValue('assets', assetor)

        segment_names = self.page.config.get('segments')
        for name in segment_names:
            self.mapLoader(name, self._load_rendered_segment)

    def _load_rendered_segment(self, data, name):
        from piecrust.rendering import PageRenderingContext, render_page_segments

        assert self is data
        uri = self._get_uri()
        try:
            ctx = PageRenderingContext(self._page, uri)
            segs = render_page_segments(ctx)
        except Exception as e:
            logger.exception("Error rendering segments for '%s': %s" % (uri, e))
            raise

        for k, v in segs.items():
            self.mapLoader(k, None)
            self.setValue(k, v)

        if 'content.abstract' in segs:
            self.setValue('content', segs['content.abstract'])
            self.setValue('has_more', True)
            if name == 'content':
                return segs['content.abstract']

        return segs[name]

