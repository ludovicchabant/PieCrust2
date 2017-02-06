import time
import logging
from piecrust.data.assetor import Assetor
from piecrust.data.pagedata import LazyPageConfigData
from piecrust.routing import create_route_metadata
from piecrust.uriutil import split_uri


logger = logging.getLogger(__name__)


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
            route_metadata = create_route_metadata(page)
            self._route = page.app.getSourceRoute(page.source.name, route_metadata)
            self._route_metadata = route_metadata
            if self._route is None:
                raise Exception("Can't get route for page: %s" % page.path)
        return self._route.getUri(self._route_metadata)

    def _load(self):
        page = self._page
        dt = page.datetime
        page_url = self._get_uri()
        _, slug = split_uri(page.app, page_url)
        self._setValue('url', page_url)
        self._setValue('slug', slug)
        self._setValue(
                'timestamp',
                time.mktime(page.datetime.timetuple()))
        self._setValue('datetime', {
            'year': dt.year, 'month': dt.month, 'day': dt.day,
            'hour': dt.hour, 'minute': dt.minute, 'second': dt.second})
        date_format = page.app.config.get('site/date_format')
        if date_format:
            self._setValue('date', page.datetime.strftime(date_format))
        self._setValue('mtime', page.path_mtime)

        assetor = page.source.buildAssetor(page, page_url)
        self._setValue('assets', assetor)

        segment_names = page.config.get('segments')
        for name in segment_names:
            self._mapLoader(name, self._load_rendered_segment)

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
                render_result = render_page_segments(ctx)
                segs = render_result.segments
            except Exception as ex:
                logger.exception(ex)
                raise Exception(
                        "Error rendering segments for '%s'" % uri) from ex
        else:
            segs = {}
            for name in self._page.config.get('segments'):
                segs[name] = "<unavailable: current page>"

        for k, v in segs.items():
            self._unmapLoader(k)
            self._setValue(k, v)

        if 'content.abstract' in segs:
            self._setValue('content', segs['content.abstract'])
            self._setValue('has_more', True)
            if name == 'content':
                return segs['content.abstract']

        return segs[name]

