import time
import logging
from piecrust.data.pagedata import LazyPageConfigData
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


class PaginationData(LazyPageConfigData):
    def __init__(self, page):
        super().__init__(page)

    def _load(self):
        from piecrust.uriutil import split_uri

        page = self._page
        dt = page.datetime
        set_val = self._setValue

        page_url = page.getUri()
        _, slug = split_uri(page.app, page_url)
        set_val('url', page_url)
        set_val('slug', slug)
        set_val('timestamp', time.mktime(page.datetime.timetuple()))
        set_val('datetime', {
            'year': dt.year, 'month': dt.month, 'day': dt.day,
            'hour': dt.hour, 'minute': dt.minute, 'second': dt.second})
        set_val('mtime', page.content_mtime)

        self._mapLoader('date', _load_date)
        self._mapLoader('assets', _load_assets)

        segment_names = page.config.get('segments')
        for name in segment_names:
            self._mapLoader(name, _load_rendered_segment)


def _load_assets(data, name):
    from piecrust.data.assetor import Assetor
    return Assetor(data._page)


def _load_date(data, name):
    page = data._page
    date_format = page.app.config.get('site/date_format')
    if date_format:
        return page.datetime.strftime(date_format)
    return None


def _load_rendered_segment(data, name):
    page = data._page

    do_render = True
    stack = page.app.env.render_ctx_stack
    if stack.hasPage(page):
        # This is the pagination data for the page that is currently
        # being rendered! Inception! But this is possible... so just
        # prevent infinite recursion.
        do_render = False

    if do_render:
        uri = page.getUri()
        try:
            from piecrust.rendering import (
                RenderingContext, render_page_segments)
            ctx = RenderingContext(page)
            render_result = render_page_segments(ctx)
            segs = render_result.segments
        except AbortedSourceUseError:
            raise
        except Exception as ex:
            logger.exception(ex)
            raise Exception(
                "Error rendering segments for '%s'" % uri) from ex
    else:
        segs = {}
        for name in page.config.get('segments'):
            segs[name] = "<unavailable: current page>"

    unmap_loader = data._unmapLoader
    set_val = data._setValue

    for k, v in segs.items():
        unmap_loader(k)
        set_val(k, v)

    if 'content.abstract' in segs:
        set_val('content', segs['content.abstract'])
        set_val('has_more', True)
        if name == 'content':
            return segs['content.abstract']

    return segs[name]

