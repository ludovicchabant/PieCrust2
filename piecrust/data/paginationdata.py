import copy
import time
import logging
from piecrust.data.pagedata import LazyPageConfigData
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


class PaginationData(LazyPageConfigData):
    def __init__(self, page, extra_data=None):
        super().__init__(page)
        if extra_data:
            self._values.update(extra_data)

    def _load(self):
        from piecrust.uriutil import split_uri

        page = self._page
        set_val = self._setValue

        page_url = page.getUri()
        _, rel_url = split_uri(page.app, page_url)
        set_val('url', page_url)
        set_val('rel_url', rel_url)
        set_val('slug', rel_url)  # For backwards compatibility
        set_val('route', copy.deepcopy(page.source_metadata['route_params']))

        self._mapLoader('date', _load_date)
        self._mapLoader('datetime', _load_datetime)
        self._mapLoader('timestamp', _load_timestamp)
        self._mapLoader('mtime', _load_content_mtime)
        self._mapLoader('assets', _load_assets)
        self._mapLoader('family', _load_family)

        segment_names = page.config.get('segments')
        for name in segment_names:
            self._mapLoader('raw_' + name, _load_raw_segment)
            self._mapLoader(name, _load_rendered_segment)


def _load_assets(data, name):
    from piecrust.data.assetor import Assetor
    return Assetor(data._page)


def _load_family(data, name):
    from piecrust.data.linker import Linker
    return Linker(data._page.source, data._page.content_item)


def _load_date(data, name):
    page = data._page
    date_format = page.app.config.get('site/date_format')
    if date_format:
        return page.datetime.strftime(date_format)
    return None


def _load_datetime(data, name):
    dt = data._page.datetime
    return {
        'year': dt.year, 'month': dt.month, 'day': dt.day,
        'hour': dt.hour, 'minute': dt.minute, 'second': dt.second}


def _load_timestamp(data, name):
    page = data._page
    return time.mktime(page.datetime.timetuple())


def _load_content_mtime(data, name):
    return data._page.content_mtime


def _load_raw_segment(data, name):
    page = data._page
    return page.getSegment(name[4:])


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

