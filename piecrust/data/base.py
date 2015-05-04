import copy
import time
import logging
from piecrust.data.assetor import Assetor
from piecrust.uriutil import split_uri


logger = logging.getLogger(__name__)


class LazyPageConfigData(object):
    """ An object that represents the configuration header of a page,
        but also allows for additional data. It's meant to be exposed
        to the templating system.
    """
    debug_render = []
    debug_render_dynamic = ['_debugRenderKeys']

    def __init__(self, page):
        self._page = page
        self._values = None
        self._loaders = None

    @property
    def page(self):
        return self._page

    def get(self, name):
        try:
            return self._getValue(name)
        except KeyError:
            return None

    def __getattr__(self, name):
        try:
            return self._getValue(name)
        except KeyError:
            raise AttributeError

    def __getitem__(self, name):
        return self._getValue(name)

    def _getValue(self, name):
        self._load()

        if self._loaders:
            loader = self._loaders.get(name)
            if loader is not None:
                try:
                    self._values[name] = loader(self, name)
                except Exception as ex:
                    raise Exception(
                            "Error while loading attribute '%s' for: %s" %
                            (name, self._page.rel_path)) from ex

                # We need to double-check `_loaders` here because
                # the loader could have removed all loaders, which
                # would set this back to `None`.
                if self._loaders is not None:
                    del self._loaders[name]
                    if len(self._loaders) == 0:
                        self._loaders = None

            elif name not in self._values:
                loader = self._loaders.get('*')
                if loader is not None:
                    try:
                        self._values[name] = loader(self, name)
                    except Exception as ex:
                        raise Exception(
                                "Error while loading attirbute '%s' for: %s" %
                                (name, self._page.rel_path)) from ex

        return self._values[name]

    def _setValue(self, name, value):
        if self._values is None:
            raise Exception("Can't call _setValue before this data has been "
                            "loaded")
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
            raise Exception(
                    "A loader has already been mapped for: %s" % attr_name)
        self._loaders[attr_name] = loader

    def _load(self):
        if self._values is not None:
            return
        self._values = self._page.config.getDeepcopy(self._page.app.debug)
        try:
            self._loadCustom()
        except Exception as ex:
            raise Exception(
                    "Error while loading data for: %s" %
                    self._page.rel_path) from ex

    def _loadCustom(self):
        pass

    def _debugRenderKeys(self):
        self._load()
        keys = set(self._values.keys())
        if self._loaders:
            keys |= set(self._loaders.keys())
        return list(keys)


class PaginationData(LazyPageConfigData):
    def __init__(self, page):
        super(PaginationData, self).__init__(page)
        self._route = None
        self._route_metadata = None

    def _get_uri(self):
        page = self._page
        if self._route is None:
            # TODO: this is not quite correct, as we're missing parts of the
            #       route metadata if the current page is a taxonomy page.
            self._route = page.app.getRoute(page.source.name,
                                            page.source_metadata)
            self._route_metadata = copy.deepcopy(page.source_metadata)
            if self._route is None:
                raise Exception("Can't get route for page: %s" % page.path)
        return self._route.getUri(self._route_metadata, provider=page)

    def _loadCustom(self):
        page_url = self._get_uri()
        _, slug = split_uri(self.page.app, page_url)
        self._setValue('url', page_url)
        self._setValue('slug', slug)
        self._setValue(
                'timestamp',
                time.mktime(self.page.datetime.timetuple()))
        date_format = self.page.app.config.get('site/date_format')
        if date_format:
            self._setValue('date', self.page.datetime.strftime(date_format))

        assetor = Assetor(self.page, page_url)
        self._setValue('assets', assetor)

        segment_names = self.page.config.get('segments')
        for name in segment_names:
            self.mapLoader(name, self._load_rendered_segment)

    def _load_rendered_segment(self, data, name):
        do_render = True
        eis = self._page.app.env.exec_info_stack
        if eis is not None and eis.hasPage(self._page):
            # This is the pagination data for the page that is currently
            # being rendered! Inception! But this is possible... so just
            # prevent infinite recursion.
            do_render = False

        assert self is data

        if do_render:
            uri = self._get_uri()
            try:
                from piecrust.rendering import (
                        QualifiedPage, PageRenderingContext,
                        render_page_segments)
                qp = QualifiedPage(self._page, self._route,
                                   self._route_metadata)
                ctx = PageRenderingContext(qp)
                segs = render_page_segments(ctx)
            except Exception as e:
                raise Exception(
                        "Error rendering segments for '%s'" % uri) from e
        else:
            segs = {}
            for name in self.page.config.get('segments'):
                segs[name] = "<unavailable: current page>"

        for k, v in segs.items():
            self.mapLoader(k, None)
            self._setValue(k, v)

        if 'content.abstract' in segs:
            self._setValue('content', segs['content.abstract'])
            self._setValue('has_more', True)
            if name == 'content':
                return segs['content.abstract']

        return segs[name]

