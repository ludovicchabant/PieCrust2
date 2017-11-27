import logging
from piecrust.data.assetor import Assetor
from piecrust.data.base import MergedMapping
from piecrust.data.linker import Linker
from piecrust.data.pagedata import PageData
from piecrust.data.paginator import Paginator
from piecrust.data.piecrustdata import PieCrustData
from piecrust.data.providersdata import DataProvidersData
from piecrust.routing import RouteFunction


logger = logging.getLogger(__name__)


class DataBuildingContext:
    def __init__(self, page, sub_num):
        self.page = page
        self.sub_num = sub_num
        self.pagination_source = None
        self.pagination_filter = None


def build_page_data(ctx):
    page = ctx.page
    sub_num = ctx.sub_num
    app = page.app

    pgn_source = ctx.pagination_source or get_default_pagination_source(page)

    pc_data = PieCrustData()
    config_data = PageData(page, ctx)
    paginator = Paginator(pgn_source, page, sub_num,
                          pgn_filter=ctx.pagination_filter)
    assetor = Assetor(page)
    linker = Linker(page.source, page.content_item)
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
            data[name] = RouteFunction(route)
        elif isinstance(func, RouteFunction):
            if not func._isCompatibleRoute(route):
                raise Exception(
                    "Route function '%s' can't target both route '%s' and "
                    "route '%s' as the 2 patterns are incompatible." %
                    (name, func._route.uri_pattern, route.uri_pattern))
        else:
            raise Exception("Route function '%s' collides with an "
                            "existing function or template data." %
                            name)

    # TODO: handle slugified taxonomy terms.

    site_data = app.config.getAll()
    providers_data = DataProvidersData(page)

    # Put the site data first so that `MergedMapping` doesn't load stuff
    # for nothing just to find a value that was in the YAML config all
    # along.
    data = MergedMapping([site_data, data, providers_data])

    # Do this at the end because we want all the data to be ready to be
    # displayed in the debugger window.
    if (app.config.get('site/show_debug_info') and
            not app.config.get('baker/is_baking')):
        pc_data.enableDebugInfo(page)

    return data


def add_layout_data(page_data, contents):
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

