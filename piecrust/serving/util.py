import re
import os.path
import hashlib
import logging
import datetime
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file
from piecrust.app import PieCrust
from piecrust.rendering import QualifiedPage
from piecrust.routing import RouteNotFoundError
from piecrust.sources.base import MODE_PARSING
from piecrust.sources.pageref import PageNotFoundError
from piecrust.uriutil import split_sub_uri


logger = logging.getLogger(__name__)


def get_app_for_server(root_dir, debug=False, theme_site=False,
                       sub_cache_dir=None, root_url='/'):
    app = PieCrust(root_dir=root_dir, debug=debug, theme_site=theme_site)
    if sub_cache_dir:
        app._useSubCacheDir(sub_cache_dir)
    app.config.set('site/root', root_url)
    app.config.set('server/is_serving', True)
    return app


class RequestedPage(object):
    def __init__(self, qualified_page):
        self.qualified_page = qualified_page
        self.req_path = None
        self.page_num = 1
        self.not_found_errors = []


def find_routes(routes, uri):
    res = []
    tax_res = []
    for route in routes:
        metadata = route.matchUri(uri)
        if metadata is not None:
            if route.is_taxonomy_route:
                tax_res.append((route, metadata))
            else:
                res.append((route, metadata))
    return res + tax_res


def get_requested_page(app, req_path):
    # Try to find what matches the requested URL.
    req_path, page_num = split_sub_uri(app, req_path)

    routes = find_routes(app.routes, req_path)
    if len(routes) == 0:
        raise RouteNotFoundError("Can't find route for: %s" % req_path)

    qp = None
    not_found_errors = []
    for route, route_metadata in routes:
        try:
            qp = _get_requested_page_for_route(
                    app, route, route_metadata, req_path)
            if qp is not None:
                break
        except PageNotFoundError as nfe:
            not_found_errors.append(nfe)

    req_page = RequestedPage(qp)
    req_page.req_path = req_path
    req_page.page_num = page_num
    req_page.not_found_errors = not_found_errors
    return req_page


def _get_requested_page_for_route(app, route, route_metadata, req_path):
    taxonomy = None
    source = app.getSource(route.source_name)
    if route.taxonomy_name is None:
        factory = source.findPageFactory(route_metadata, MODE_PARSING)
        if factory is None:
            raise PageNotFoundError("No path found for '%s' in source '%s'." %
                                    (req_path, source.name))
    else:
        taxonomy = app.getTaxonomy(route.taxonomy_name)

        # This will raise `PageNotFoundError` naturally if not found.
        tax_page_ref = taxonomy.getPageRef(source)
        factory = tax_page_ref.getFactory()

    # Build the page.
    page = factory.buildPage()
    qp = QualifiedPage(page, route, route_metadata)
    return qp


def load_mimetype_map():
    mimetype_map = {}
    sep_re = re.compile(r'\s+')
    path = os.path.join(os.path.dirname(__file__), 'mime.types')
    with open(path, 'r') as f:
        for line in f:
            tokens = sep_re.split(line)
            if len(tokens) > 1:
                for t in tokens[1:]:
                    mimetype_map[t] = tokens[0]
    return mimetype_map


def make_wrapped_file_response(environ, request, path):
    logger.debug("Serving %s" % path)

    # Check if we can return a 304 status code.
    mtime = os.path.getmtime(path)
    etag_str = '%s$$%s' % (path, mtime)
    etag = hashlib.md5(etag_str.encode('utf8')).hexdigest()
    if etag in request.if_none_match:
        response = Response()
        response.status_code = 304
        return response

    wrapper = wrap_file(environ, open(path, 'rb'))
    response = Response(wrapper)
    _, ext = os.path.splitext(path)
    response.set_etag(etag)
    response.last_modified = datetime.datetime.fromtimestamp(mtime)
    response.mimetype = mimetype_map.get(
            ext.lstrip('.'), 'text/plain')
    response.direct_passthrough = True
    return response


mimetype_map = load_mimetype_map()
content_type_map = {
        'html': 'text/html',
        'xml': 'text/xml',
        'txt': 'text/plain',
        'text': 'text/plain',
        'css': 'text/css',
        'xhtml': 'application/xhtml+xml',
        'atom': 'application/atom+xml',  # or 'text/xml'?
        'rss': 'application/rss+xml',    # or 'text/xml'?
        'json': 'application/json'}

