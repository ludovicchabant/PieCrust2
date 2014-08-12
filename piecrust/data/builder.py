import time
import logging
from piecrust.configuration import merge_dicts
from piecrust.data.assetor import Assetor
from piecrust.data.debug import build_debug_info
from piecrust.data.linker import Linker
from piecrust.data.paginator import Paginator


logger = logging.getLogger(__name__)


class DataBuildingContext(object):
    def __init__(self, page, uri, page_num=1):
        self.page = page
        self.uri = uri
        self.page_num = page_num
        self.pagination_source = None
        self.pagination_filter = None


def build_page_data(ctx):
    page = ctx.page
    app = page.app

    pgn_source = ctx.pagination_source or get_default_pagination_source(page)
    paginator = Paginator(page, pgn_source, ctx.uri, ctx.page_num,
            ctx.pagination_filter)
    assetor = Assetor(page, ctx.uri)
    linker = Linker(page)
    data = {
            'piecrust': build_piecrust_data(),
            'page': dict(page.config.get()),
            'assets': assetor,
            'pagination': paginator,
            'siblings': linker,
            'family': linker
            }
    page_data = data['page']
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
    if (app.debug and app.config.get('site/enable_debug_info') and
            not app.config.get('baker/is_baking')):
        data['piecrust']['debug_info'] = build_debug_info(page, data)

    return data


def build_layout_data(page, page_data, contents):
    data = dict(page_data)
    for name, txt in contents.items():
        if name in data:
            logger.warning("Content segment '%s' will hide existing data." %
                    name)
        data[name] = txt
    return data


try:
    from piecrust.__version__ import VERSION
except ImportError:
    from piecrust import APP_VERSION as VERSION


def build_piecrust_data():
    data = {
            'version': VERSION,
            'url': 'http://bolt80.com/piecrust/',
            'branding': 'Baked with <em><a href="%s">PieCrust</a> %s</em>.' % (
                'http://bolt80.com/piecrust/', VERSION)
            }
    return data


def build_site_data(page):
    app = page.app
    data = dict(app.config.get())
    for source in app.sources:
        endpoint_bits = source.data_endpoint.split('/')
        endpoint = data
        for e in endpoint_bits[:-1]:
            if e not in endpoint:
                endpoint[e] = {}
            endpoint = endpoint[e]
        user_data = endpoint.get(endpoint_bits[-1])
        provider = source.buildDataProvider(page, user_data)
        if endpoint_bits[-1] in endpoint:
            provider.user_data = endpoint[endpoint_bits[-1]]
        endpoint[endpoint_bits[-1]] = provider
    return data


def get_default_pagination_source(page):
    app = page.app
    source_name = page.config.get('source') or page.config.get('blog')
    logger.debug("Got source name %s for page %s" % (source_name, page.path))
    if source_name is None:
        blog_names = app.config.get('site/blogs')
        if blog_names is not None:
            source_name = blog_names[0]
        else:
            source_name = app.sources[0].name
    source = app.getSource(source_name)
    return source

