import logging
from werkzeug.utils import cached_property
from piecrust.data.base import MergedMapping
from piecrust.data.linker import PageLinkerData
from piecrust.data.pagedata import PageData
from piecrust.data.paginator import Paginator
from piecrust.data.piecrustdata import PieCrustData
from piecrust.data.providersdata import DataProvidersData
from piecrust.routing import CompositeRouteFunction


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
    pgn_source = ctx.pagination_source or get_default_pagination_source(page)
    first_uri = ctx.page.getUri(1)

    pc_data = PieCrustData()
    config_data = PageData(page, ctx)
    paginator = Paginator(page, pgn_source,
                          page_num=ctx.page_num,
                          pgn_filter=ctx.pagination_filter)
    assetor = page.source.buildAssetor(page, first_uri)
    linker = PageLinkerData(page.source, page.rel_path)
    data = {
            'piecrust': pc_data,
            'page': config_data,
            'assets': assetor,
            'pagination': paginator,
            'family': linker
            }

    for route in app.routes:
        name = route.func_name
        if not name:
            continue

        func = data.get(name)
        if func is None:
            func = CompositeRouteFunction()
            func.addFunc(route)
            data[name] = func
        elif isinstance(func, CompositeRouteFunction):
            func.addFunc(route)
        else:
            raise Exception("Route function '%s' collides with an "
                            "existing function or template data." %
                            name)

    #TODO: handle slugified taxonomy terms.

    site_data = app.config.getAll()
    providers_data = DataProvidersData(page)
    data = MergedMapping([data, providers_data, site_data])

    # Do this at the end because we want all the data to be ready to be
    # displayed in the debugger window.
    if (app.config.get('site/show_debug_info') and
            not app.config.get('baker/is_baking')):
        pc_data.enableDebugInfo(page)

    return data


def build_layout_data(page, page_data, contents):
    for name, txt in contents.items():
        if name in page_data:
            logger.warning("Content segment '%s' will hide existing data." %
                           name)
    page_data._prependMapping(contents)


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

