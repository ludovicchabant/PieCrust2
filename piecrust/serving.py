import re
import gzip
import time
import os
import os.path
import hashlib
import logging
import io
from werkzeug.exceptions import (NotFound, MethodNotAllowed,
        InternalServerError)
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import wrap_file
from jinja2 import FileSystemLoader, Environment
from piecrust.app import PieCrust
from piecrust.data.filters import (PaginationFilter, HasFilterClause,
        IsFilterClause)
from piecrust.page import Page
from piecrust.processing.base import ProcessorPipeline
from piecrust.rendering import PageRenderingContext, render_page
from piecrust.sources.base import PageFactory, MODE_PARSING


logger = logging.getLogger(__name__)


class Server(object):
    def __init__(self, root_dir, host='localhost', port='8080',
                 debug=False, static_preview=True):
        self.root_dir = root_dir
        self.host = host
        self.port = port
        self.debug = debug
        self.static_preview = static_preview
        self._out_dir = None
        self._skip_patterns = None
        self._force_patterns = None
        self._record = None
        self._mimetype_map = load_mimetype_map()

    def run(self):
        # Bake all the assets so we know what we have, and so we can serve
        # them to the client. We need a temp app for this.
        app = PieCrust(root_dir=self.root_dir, debug=self.debug)
        mounts = app.assets_dirs
        self._out_dir = os.path.join(app.cache_dir, 'server')
        self._skip_patterns = app.config.get('baker/skip_patterns')
        self._force_patterns = app.config.get('baker/force_patterns')
        pipeline = ProcessorPipeline(
                app, mounts, self._out_dir,
                skip_patterns=self._skip_patterns,
                force_patterns=self._force_patterns)
        self._record = pipeline.run()

        # Run the WSGI app.
        wsgi_wrapper = WsgiServer(self)
        run_simple(self.host, self.port, wsgi_wrapper,
                   use_debugger=True, use_reloader=True)

    def _run_request(self, environ, start_response):
        try:
            return self._run_piecrust(environ, start_response)
        except Exception as ex:
            if self.debug:
                raise
            return self._handle_error(ex, environ, start_response)

    def _run_piecrust(self, environ, start_response):
        request = Request(environ)

        # We don't support anything else than GET requests since we're
        # previewing something that will be static later.
        if self.static_preview and request.method != 'GET':
            logger.error("Only GET requests are allowed, got %s" % request.method)
            raise MethodNotAllowed()

        # Create the app for this request.
        app = PieCrust(root_dir=self.root_dir, debug=self.debug)
        app.config.set('site/root', '/')
        app.config.set('site/pretty_urls', True)
        app.config.set('server/is_serving', True)

        # We'll serve page assets directly from where they are.
        app.env.base_asset_url_format = '/_asset/%path%'

        # See if the requested URL is an asset.
        response = self._try_serve_asset(app, environ, request)
        if response is not None:
            return response(environ, start_response)

        # It's not an asset we know of... let's see if it can be a page asset.
        response = self._try_serve_page_asset(app, environ, request)
        if response is not None:
            return response(environ, start_response)

        # Nope. Let's hope it's an actual page.
        try:
            response = self._try_serve_page(app, environ, request)
            return response(environ, start_response)
        except (RouteNotFoundError, SourceNotFoundError) as ex:
            logger.exception(ex)
            raise NotFound()
        except Exception as ex:
            logger.exception(ex)
            if app.debug:
                raise
            raise InternalServerError()

    def _try_serve_asset(self, app, environ, request):
        logger.debug("Searching for asset with path: %s" % request.path)
        rel_req_path = request.path.lstrip('/').replace('/', os.sep)
        entry = self._record.findEntry(rel_req_path)
        if entry is None:
            return None

        # Yep, we know about this URL because we processed an asset that
        # maps to it... make sure it's up to date by re-processing it
        # before serving.
        mounts = app.assets_dirs
        asset_in_path = entry.path
        asset_out_path = os.path.join(self._out_dir, rel_req_path)
        pipeline = ProcessorPipeline(
                app, mounts, self._out_dir,
                skip_patterns=self._skip_patterns,
                force_patterns=self._force_patterns)
        pipeline.run(asset_in_path)

        logger.debug("Serving %s" % asset_out_path)
        wrapper = wrap_file(environ, open(asset_out_path, 'rb'))
        response = Response(wrapper)
        _, ext = os.path.splitext(rel_req_path)
        response.mimetype = self._mimetype_map.get(
                ext.lstrip('.'), 'text/plain')
        return response

    def _try_serve_page_asset(self, app, environ, request):
        if not request.path.startswith('/_asset/'):
            return None

        full_path = os.path.join(app.root_dir, request.path[len('/_asset/'):])
        if not os.path.isfile(full_path):
            return None

        logger.debug("Serving %s" % full_path)
        wrapper = wrap_file(environ, open(full_path, 'rb'))
        response = Response(wrapper)
        _, ext = os.path.splitext(full_path)
        response.mimetype = self._mimetype_map.get(
                ext.lstrip('.'), 'text/plain')
        return response

    def _try_serve_page(self, app, environ, request):
        # Try to find what matches the requested URL.
        req_path = request.path
        page_num = 1
        pgn_suffix_re = app.config.get('__cache/pagination_suffix_re')
        pgn_suffix_m = re.search(pgn_suffix_re, request.path)
        if pgn_suffix_m:
            req_path = request.path[:pgn_suffix_m.start()]
            page_num = int(pgn_suffix_m.group('num'))

        routes = find_routes(app.routes, req_path)
        if len(routes) == 0:
            raise RouteNotFoundError("Can't find route for: %s" % req_path)

        taxonomy = None
        for route, route_metadata in routes:
            source = app.getSource(route.source_name)
            if route.taxonomy is None:
                rel_path, fac_metadata = source.findPagePath(
                        route_metadata, MODE_PARSING)
                if rel_path is not None:
                    break
            else:
                taxonomy = app.getTaxonomy(route.taxonomy)
                term_value = route_metadata.get(taxonomy.term_name)
                if term_value is not None:
                    tax_page_ref = taxonomy.getPageRef(source.name)
                    rel_path = tax_page_ref.rel_path
                    source = tax_page_ref.source
                    fac_metadata = {taxonomy.term_name: term_value}
                    break
        else:
            raise SourceNotFoundError("Can't find path for: %s "
                    "(looked in: %s)" %
                    (req_path, [r.source_name for r, _ in routes]))

        # Build the page and render it.
        fac = PageFactory(source, rel_path, fac_metadata)
        page = fac.buildPage()
        render_ctx = PageRenderingContext(page, req_path, page_num)
        if taxonomy is not None:
            flt = PaginationFilter()
            if taxonomy.is_multiple:
                flt.addClause(HasFilterClause(taxonomy.name, term_value))
            else:
                flt.addClause(IsFilterClause(taxonomy.name, term_value))
            render_ctx.pagination_filter = flt

            render_ctx.custom_data = {
                    taxonomy.term_name: term_value}
        rendered_page = render_page(render_ctx)
        rp_content = rendered_page.content

        if app.debug:
            now_time = time.clock()
            timing_info = ('%8.1f ms' %
                    ((now_time - app.env.start_time) * 1000.0))
            rp_content = rp_content.replace('__PIECRUST_TIMING_INFORMATION__',
                    timing_info)

        # Start response.
        response = Response()

        etag = hashlib.md5(rp_content.encode('utf8')).hexdigest()
        if not app.debug and etag in request.if_none_match:
            response.status_code = 304
            return response

        response.set_etag(etag)
        response.content_md5 = etag

        cache_control = response.cache_control
        if app.debug:
            cache_control.no_cache = True
            cache_control.must_revalidate = True
        else:
            cache_time = (page.config.get('cache_time') or
                    app.config.get('site/cache_time'))
            if cache_time:
                cache_control.public = True
                cache_control.max_age = cache_time

        content_type = page.config.get('content_type')
        if content_type and '/' not in content_type:
            mimetype = content_type_map.get(content_type, content_type)
        else:
            mimetype = content_type
        if mimetype:
            response.mimetype = mimetype

        if ('gzip' in request.accept_encodings and
                app.config.get('site/enable_gzip')):
            try:
                with io.BytesIO() as gzip_buffer:
                    with gzip.open(gzip_buffer, mode='wt',
                                   encoding='utf8') as gzip_file:
                        gzip_file.write(rp_content)
                    rp_content = gzip_buffer.getvalue()
                    response.content_encoding = 'gzip'
            except Exception:
                logger.exception("Error compressing response, "
                                 "falling back to uncompressed.")
        response.set_data(rp_content)

        return response

    def _handle_error(self, exception, environ, start_response):
        path = 'error'
        if isinstance(exception, NotFound):
            path = '404'
        env = Environment(loader=ErrorMessageLoader())
        template = env.get_template(path)
        context = {'details': str(exception)}
        response = Response(template.render(context), mimetype='text/html')
        return response(environ, start_response)


class WsgiServer(object):
    def __init__(self, server):
        self.server = server

    def __call__(self, environ, start_response):
        return self.server._run_request(environ, start_response)


class RouteNotFoundError(Exception):
    pass


class SourceNotFoundError(Exception):
    pass


content_type_map = {
        'html': 'text/html',
        'xml': 'text/xml',
        'txt': 'text/plain',
        'text': 'text/plain',
        'css': 'text/css',
        'xhtml': 'application/xhtml+xml',
        'atom': 'application/atom+xml', # or 'text/xml'?
        'rss': 'application/rss+xml',   # or 'text/xml'?
        'json': 'application/json'}


def find_routes(routes, uri):
    uri = uri.lstrip('/')
    res = []
    for route in routes:
        m = route.uri_re.match(uri)
        if m:
            metadata = m.groupdict()
            res.append((route, metadata))
    return res


class ErrorMessageLoader(FileSystemLoader):
    def __init__(self):
        base_dir = os.path.join(os.path.dirname(__file__), 'resources',
                                'messages')
        super(ErrorMessageLoader, self).__init__(base_dir)

    def get_source(self, env, template):
        template += '.html'
        return super(ErrorMessageLoader, self).get_source(env, template)


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

