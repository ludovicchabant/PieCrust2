import re
import os.path
import hashlib
import logging
import datetime
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file
from piecrust.page import PageNotFoundError
from piecrust.routing import RouteNotFoundError
from piecrust.uriutil import split_sub_uri


logger = logging.getLogger(__name__)


def get_app_for_server(appfactory, root_url='/'):
    app = appfactory.create()
    app.config.set('site/root', root_url)
    app.config.set('server/is_serving', True)
    # We'll serve page assets directly from where they are.
    app.config.set('site/asset_url_format', root_url + '_asset/%path%')
    return app


class RequestedPage(object):
    def __init__(self):
        self.page = None
        self.sub_num = 1
        self.req_path = None
        self.not_found_errors = []


def find_routes(routes, uri, decomposed_uri=None):
    """ Returns routes matching the given URL.
    """
    sub_num = 0
    uri_no_sub = None
    if decomposed_uri is not None:
        uri_no_sub, sub_num = decomposed_uri

    res = []
    for route in routes:
        route_params = route.matchUri(uri)
        if route_params is not None:
            res.append((route, route_params, 1))

        if sub_num > 1:
            route_params = route.matchUri(uri_no_sub)
            if route_params is not None:
                res.append((route, route_params, sub_num))
    return res


def get_requested_page(app, req_path):
    # Remove the trailing slash to simplify how we parse URLs.
    root_url = app.config.get('site/root')
    if req_path != root_url:
        req_path = req_path.rstrip('/')

    # Try to find what matches the requested URL.
    # It could also be a sub-page (i.e. the URL ends with a page number), so
    # we try to also match the base URL (without the number).
    req_path_no_sub, sub_num = split_sub_uri(app, req_path)
    routes = find_routes(app.routes, req_path, (req_path_no_sub, sub_num))
    if len(routes) == 0:
        raise RouteNotFoundError("Can't find route for: %s" % req_path)

    req_page = RequestedPage()
    for route, route_params, route_sub_num in routes:
        cur_req_path = req_path
        if route_sub_num > 1:
            cur_req_path = req_path_no_sub

        page = _get_requested_page_for_route(app, route, route_params)
        if page is not None:
            req_page.page = page
            req_page.sub_num = route_sub_num
            req_page.req_path = cur_req_path
            break

        req_page.not_found_errors.append(PageNotFoundError(
            "No path found for '%s' in source '%s'." %
            (cur_req_path, route.source_name)))

    return req_page


def _get_requested_page_for_route(app, route, route_params):
    source = app.getSource(route.source_name)
    item = source.findContentFromRoute(route_params)
    if item is not None:
        return app.getPage(source, item)
    return None


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
    # Check if we can return a 304 status code.
    mtime = os.path.getmtime(path)
    etag_str = '%s$$%s' % (path, mtime)
    etag = hashlib.md5(etag_str.encode('utf8')).hexdigest()
    if etag in request.if_none_match:
        logger.debug("Serving %s [no download, E-Tag matches]" % path)
        response = Response()
        response.status_code = 304
        return response

    logger.debug("Serving %s [full download]" % path)
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

