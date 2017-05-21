import time
import logging
from piecrust.data.pagedata import LazyPageConfigData


logger = logging.getLogger(__name__)


class PaginationData(LazyPageConfigData):
    def __init__(self, page):
        super().__init__(page)

    def _load(self):
        from piecrust.data.assetor import Assetor
        from piecrust.uriutil import split_uri

        page = self._page
        dt = page.datetime
        page_url = page.getUri()
        _, slug = split_uri(page.app, page_url)
        self._setValue('url', page_url)
        self._setValue('slug', slug)
        self._setValue('timestamp',
                       time.mktime(page.datetime.timetuple()))
        self._setValue('datetime', {
            'year': dt.year, 'month': dt.month, 'day': dt.day,
            'hour': dt.hour, 'minute': dt.minute, 'second': dt.second})
        date_format = page.app.config.get('site/date_format')
        if date_format:
            self._setValue('date', page.datetime.strftime(date_format))
        self._setValue('mtime', page.content_mtime)

        assetor = Assetor(page)
        self._setValue('assets', assetor)

        segment_names = page.config.get('segments')
        for name in segment_names:
            self._mapLoader(name, self._load_rendered_segment)

    def _load_rendered_segment(self, data, name):
        do_render = True
        stack = self._page.app.env.render_ctx_stack
        if stack.hasPage(self._page):
            # This is the pagination data for the page that is currently
            # being rendered! Inception! But this is possible... so just
            # prevent infinite recursion.
            do_render = False

        assert self is data

        if do_render:
            uri = self.getUri()
            try:
                from piecrust.rendering import (
                    RenderingContext, render_page_segments)
                ctx = RenderingContext(self._page)
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

