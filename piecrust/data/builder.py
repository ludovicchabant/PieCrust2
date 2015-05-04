import re
import time
import copy
import logging
from werkzeug.utils import cached_property
from piecrust import APP_VERSION
from piecrust.configuration import merge_dicts
from piecrust.data.assetor import Assetor
from piecrust.data.debug import build_debug_info
from piecrust.data.linker import PageLinkerData
from piecrust.data.paginator import Paginator
from piecrust.uriutil import split_sub_uri


logger = logging.getLogger(__name__)


class DataBuildingContext(object):
    def __init__(self, qualified_page, page_num=1):
        self.page = qualified_page
        self.page_num = page_num
        self.pagination_source = None
        self.pagination_filter = None

    @property
    def app(self):
        return self.page.app

    @cached_property
    def uri(self):
        return self.page.getUri(self.page_num)


def build_page_data(ctx):
    app = ctx.app
    page = ctx.page
    first_uri, _ = split_sub_uri(app, ctx.uri)

    pc_data = PieCrustData()
    pgn_source = ctx.pagination_source or get_default_pagination_source(page)
    paginator = Paginator(page, pgn_source,
                          page_num=ctx.page_num,
                          pgn_filter=ctx.pagination_filter)
    assetor = Assetor(page, first_uri)
    linker = PageLinkerData(page.source, page.rel_path)
    data = {
            'piecrust': pc_data,
            'page': {},
            'assets': assetor,
            'pagination': paginator,
            'family': linker
            }
    page_data = data['page']
    page_data.update(copy.deepcopy(page.source_metadata))
    page_data.update(page.config.getDeepcopy(app.debug))
    page_data['url'] = ctx.uri
    page_data['timestamp'] = time.mktime(page.datetime.timetuple())
    date_format = app.config.get('site/date_format')
    if date_format:
        page_data['date'] = page.datetime.strftime(date_format)

    #TODO: handle slugified taxonomy terms.

    site_data = build_site_data(page)
    merge_dicts(data, site_data)

    # Do this at the end because we want all the data to be ready to be
    # displayed in the debugger window.
    if (app.config.get('site/show_debug_info') and
            not app.config.get('baker/is_baking')):
        pc_data._enableDebugInfo(page, data)

    return data


def build_layout_data(page, page_data, contents):
    for name, txt in contents.items():
        if name in page_data:
            logger.warning("Content segment '%s' will hide existing data." %
                           name)
        page_data[name] = txt


class PieCrustData(object):
    debug_render = ['version', 'url', 'branding', 'debug_info']
    debug_render_invoke = ['version', 'url', 'branding', 'debug_info']
    debug_render_redirect = {'debug_info': '_debugRenderDebugInfo'}

    def __init__(self):
        self.version = APP_VERSION
        self.url = 'http://bolt80.com/piecrust/'
        self.branding = 'Baked with <em><a href="%s">PieCrust</a> %s</em>.' % (
                'http://bolt80.com/piecrust/', APP_VERSION)
        self._page = None
        self._data = None

    @property
    def debug_info(self):
        if self._page is not None and self._data is not None:
            return build_debug_info(self._page, self._data)
        return ''

    def _enableDebugInfo(self, page, data):
        self._page = page
        self._data = data

    def _debugRenderDebugInfo(self):
        return "The very thing you're looking at!"


re_endpoint_sep = re.compile(r'[\/\.]')


def build_site_data(page):
    app = page.app
    data = app.config.getDeepcopy(app.debug)
    for source in app.sources:
        endpoint_bits = re_endpoint_sep.split(source.data_endpoint)
        endpoint = data
        for e in endpoint_bits[:-1]:
            if e not in endpoint:
                endpoint[e] = {}
            endpoint = endpoint[e]
        user_data = endpoint.get(endpoint_bits[-1])
        provider = source.buildDataProvider(page, user_data)
        endpoint[endpoint_bits[-1]] = provider
    return data


def get_default_pagination_source(page):
    app = page.app
    source_name = page.config.get('source') or page.config.get('blog')
    if source_name is None:
        source_name = app.config.get('site/default_pagination_source')
    if source_name is None:
        blog_names = app.config.get('site/blogs')
        if blog_names is not None:
            source_name = blog_names[0]
        else:
            source_name = app.sources[0].name
    source = app.getSource(source_name)
    return source

