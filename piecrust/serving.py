import re
import gzip
import time
import os
import os.path
import hashlib
import logging
import io
from werkzeug.exceptions import (NotFound, MethodNotAllowed,
        InternalServerError, HTTPException)
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import wrap_file
from jinja2 import FileSystemLoader, Environment
from piecrust.app import PieCrust
from piecrust.data.filters import (PaginationFilter, HasFilterClause,
        IsFilterClause)
from piecrust.environment import StandardEnvironment
from piecrust.processing.base import ProcessorPipeline
from piecrust.rendering import PageRenderingContext, render_page
from piecrust.sources.base import PageFactory, MODE_PARSING


logger = logging.getLogger(__name__)


class ServingEnvironment(StandardEnvironment):
    pass


class ServeRecord(object):
    def __init__(self):
        self.entries = {}

    def addEntry(self, entry):
        key = self._makeKey(entry.uri, entry.sub_num)
        self.entries[key] = entry

    def getEntry(self, uri, sub_num):
        key = self._makeKey(uri, sub_num)
        return self.entries.get(key)

    def _makeKey(self, uri, sub_num):
        return "%s:%s" % (uri, sub_num)


class ServeRecordPageEntry(object):
    def __init__(self, uri, sub_num):
        self.uri = uri
        self.sub_num = sub_num
        self.used_source_names = set()


class Server(object):
    def __init__(self, root_dir, host='localhost', port='8080',
                 debug=False, use_reloader=False, static_preview=True,
                 synchronous_asset_pipeline=True):
        self.root_dir = root_dir
        self.host = host
        self.port = port
        self.debug = debug
        self.use_reloader = use_reloader
        self.static_preview = static_preview
        self.synchronous_asset_pipeline = synchronous_asset_pipeline
        self._out_dir = None
        self._asset_record = None
        self._page_record = None
        self._mimetype_map = load_mimetype_map()

    def run(self):
        # Bake all the assets so we know what we have, and so we can serve
        # them to the client. We need a temp app for this.
        app = PieCrust(root_dir=self.root_dir, debug=self.debug)
        self._out_dir = os.path.join(app.cache_dir, 'server')
        pipeline = ProcessorPipeline(app, self._out_dir)
        self._asset_record = pipeline.run()
        self._page_record = ServeRecord()

        # Run the WSGI app.
        wsgi_wrapper = WsgiServer(self)
        run_simple(self.host, self.port, wsgi_wrapper,
                   use_debugger=self.debug, use_reloader=self.use_reloader)

    def _run_request(self, environ, start_response):
        try:
            return self._try_run_request(environ, start_response)
        except Exception as ex:
            if self.debug:
                raise
            return self._handle_error(ex, environ, start_response)

    def _try_run_request(self, environ, start_response):
        request = Request(environ)

        # We don't support anything else than GET requests since we're
        # previewing something that will be static later.
        if self.static_preview and request.method != 'GET':
            logger.error("Only GET requests are allowed, got %s" % request.method)
            raise MethodNotAllowed()

        # Create the app for this request.
        rq_debug = ('!debug' in request.args)
        app = PieCrust(root_dir=self.root_dir, debug=(self.debug or rq_debug))
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

        # Nope. Let's see if it's an actual page.
        # We trap any exception that says "there's no such page" so we can
        # try another thing before bailing out. But we let any exception
        # that says "something's wrong" through.
        exc = None
        try:
            response = self._try_serve_page(app, environ, request)
            return response(environ, start_response)
        except (RouteNotFoundError, SourceNotFoundError) as ex:
            exc = NotFound(str(ex))
        except NotFound as ex:
            exc = ex
        except HTTPException:
            raise
        except Exception as ex:
            if app.debug:
                logger.exception(ex)
                raise
            msg = str(ex)
            logger.error(msg)
            raise InternalServerError(msg)

        # Nothing worked so far... let's see if there's a new asset.
        response = self._try_serve_new_asset(app, environ, request)
        if response is not None:
            return response(environ, start_response)

        # Nope. Raise the exception we had in store.
        raise exc

    def _try_serve_asset(self, app, environ, request):
        logger.debug("Searching %d entries for asset with path: %s" %
                (len(self._asset_record.entries), request.path))
        rel_req_path = request.path.lstrip('/').replace('/', os.sep)
        entry = self._asset_record.findEntry(rel_req_path)
        if entry is None:
            # We don't know any asset that could have created this path.
            # It could be a new asset that the user just created, but we'll
            # check for that later.
            # What we can do however is see if there's anything that already
            # exists there, because it could have been created by a processor
            # that bypasses structured processing (like e.g. the compass
            # processor). In that case, just return that file, hoping it will
            # be up-to-date.
            full_path = os.path.join(self._out_dir, rel_req_path)
            try:
                response = self._make_wrapped_file_response(
                        environ, full_path)
                logger.debug("Didn't find record entry, but found existing "
                             "output file at: %s" % rel_req_path)
                return response
            except OSError:
                pass
            return None

        # Yep, we know about this URL because we processed an asset that
        # maps to it... make sure it's up to date by re-processing it
        # before serving.
        asset_in_path = entry.path
        asset_out_path = os.path.join(self._out_dir, rel_req_path)

        if self.synchronous_asset_pipeline:
            logger.debug("Making sure '%s' is up-to-date." % asset_in_path)
            pipeline = ProcessorPipeline(app, self._out_dir)
            r = pipeline.run(asset_in_path, delete=False, save_record=False,
                             previous_record=self._asset_record)
            assert len(r.entries) == 1
            self._asset_record.replaceEntry(r.entries[0])

        return self._make_wrapped_file_response(environ, asset_out_path)

    def _try_serve_new_asset(self, app, environ, request):
        logger.debug("Searching for a new asset with path: %s" % request.path)
        pipeline = ProcessorPipeline(app, self._out_dir)
        r = pipeline.run(new_only=True, delete=False, save_record=False,
                         previous_record=self._asset_record)
        for e in r.entries:
            self._asset_record.addEntry(e)

        rel_req_path = request.path.lstrip('/').replace('/', os.sep)
        entry = self._asset_record.findEntry(rel_req_path)
        if entry is None:
            return None

        asset_out_path = os.path.join(self._out_dir, rel_req_path)
        logger.debug("Found new asset: %s" % entry.path)
        return self._make_wrapped_file_response(environ, asset_out_path)

    def _try_serve_page_asset(self, app, environ, request):
        if not request.path.startswith('/_asset/'):
            return None

        full_path = os.path.join(app.root_dir, request.path[len('/_asset/'):])
        if not os.path.isfile(full_path):
            return None

        return self._make_wrapped_file_response(environ, full_path)

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

        # Build the page.
        fac = PageFactory(source, rel_path, fac_metadata)
        page = fac.buildPage()
        # We force the rendering of the page because it could not have
        # changed, but include pages that did change.
        render_ctx = PageRenderingContext(page, req_path, page_num,
                                          force_render=True)
        if taxonomy is not None:
            flt = PaginationFilter()
            if taxonomy.is_multiple:
                flt.addClause(HasFilterClause(taxonomy.name, term_value))
            else:
                flt.addClause(IsFilterClause(taxonomy.name, term_value))
            render_ctx.pagination_filter = flt
            render_ctx.custom_data = {
                    taxonomy.term_name: term_value}

        # See if this page is known to use sources. If that's the case,
        # just don't use cached rendered segments for that page (but still
        # use them for pages that are included in it).
        entry = self._page_record.getEntry(req_path, page_num)
        if (taxonomy is not None or entry is None or
                entry.used_source_names):
            cache_key = '%s:%s' % (req_path, page_num)
            app.env.rendered_segments_repository.invalidate(cache_key)

        # Render the page.
        rendered_page = render_page(render_ctx)
        rp_content = rendered_page.content

        if taxonomy is not None:
            paginator = rendered_page.data.get('pagination')
            if (paginator and paginator.is_loaded and
                    len(paginator.items) == 0):
                message = ("This URL matched a route for taxonomy '%s' but "
                           "no pages have been found to have it. This page "
                           "won't be generated by a bake." % taxonomy.name)
                raise NotFound(message)

        if entry is None:
            entry = ServeRecordPageEntry(req_path, page_num)
            self._page_record.addEntry(entry)
        entry.used_source_names = set(render_ctx.used_source_names)

        # Profiling.
        if app.debug:
            now_time = time.clock()
            timing_info = ('%8.1f ms' %
                    ((now_time - app.env.start_time) * 1000.0))
            rp_content = rp_content.replace('__PIECRUST_TIMING_INFORMATION__',
                    timing_info)

        # Build the response.
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

    def _make_wrapped_file_response(self, environ, path):
        logger.debug("Serving %s" % path)
        wrapper = wrap_file(environ, open(path, 'rb'))
        response = Response(wrapper)
        _, ext = os.path.splitext(path)
        response.mimetype = self._mimetype_map.get(
                ext.lstrip('.'), 'text/plain')
        return response

    def _handle_error(self, exception, environ, start_response):
        code = 500
        path = 'error'
        description = str(exception)
        if isinstance(exception, HTTPException):
            code = exception.code
            description = exception.description
            if isinstance(exception, NotFound):
                path += '404'
        env = Environment(loader=ErrorMessageLoader())
        template = env.get_template(path)
        context = {'details': description}
        response = Response(template.render(context), mimetype='text/html')
        response.status_code = code
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
        metadata = route.matchUri(uri)
        if metadata:
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

