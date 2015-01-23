import io
import os
import re
import gzip
import time
import os.path
import hashlib
import logging
import threading
from werkzeug.exceptions import (
        NotFound, MethodNotAllowed, InternalServerError, HTTPException)
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import wrap_file
from jinja2 import FileSystemLoader, Environment
from piecrust.app import PieCrust
from piecrust.data.filters import (
        PaginationFilter, HasFilterClause, IsFilterClause)
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
    def __init__(self, root_dir, host='localhost', port=8080,
                 debug=False, use_reloader=False, static_preview=True):
        self.root_dir = root_dir
        self.host = host
        self.port = int(port)
        self.debug = debug
        self.use_reloader = use_reloader
        self.static_preview = static_preview
        self._out_dir = None
        self._page_record = None
        self._mimetype_map = load_mimetype_map()

    def run(self):
        # Bake all the assets so we know what we have, and so we can serve
        # them to the client. We need a temp app for this.
        app = PieCrust(root_dir=self.root_dir, debug=self.debug)
        self._out_dir = os.path.join(app.cache_dir, 'server')
        self._page_record = ServeRecord()

        pipeline = ProcessorPipeline(app, self._out_dir)
        loop = ProcessingLoop(pipeline)
        loop.start()

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

        # Let's see if it can be a page asset.
        response = self._try_serve_page_asset(app, environ, request)
        if response is not None:
            return response(environ, start_response)

        # Nope. Let's see if it's an actual page.
        try:
            response = self._try_serve_page(app, environ, request)
            return response(environ, start_response)
        except (RouteNotFoundError, SourceNotFoundError) as ex:
            raise NotFound(str(ex))
        except HTTPException:
            raise
        except Exception as ex:
            if app.debug:
                logger.exception(ex)
                raise
            msg = str(ex)
            logger.error(msg)
            raise InternalServerError(msg)

    def _try_serve_asset(self, app, environ, request):
        rel_req_path = request.path.lstrip('/').replace('/', os.sep)
        full_path = os.path.join(self._out_dir, rel_req_path)
        try:
            response = self._make_wrapped_file_response(
                    environ, full_path)
            return response
        except OSError:
            pass
        return None

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


class ProcessingLoop(threading.Thread):
    def __init__(self, pipeline):
        super(ProcessingLoop, self).__init__(
                name='pipeline-reloader', daemon=True)
        self.pipeline = pipeline
        self.interval = 1
        self._paths = set()
        self._record = None
        self._last_bake = 0

    def run(self):
        # Build the first list of known files and run the pipeline once.
        app = self.pipeline.app
        roots = [os.path.join(app.root_dir, r)
                 for r in self.pipeline.mounts.keys()]
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                self._paths |= set([os.path.join(dirpath, f)
                                    for f in filenames])
        self._last_bake = time.time()
        self._record = self.pipeline.run(save_record=False)

        while True:
            for root in roots:
                # For each mount root we try to find the first new or
                # modified file. If any, we just run the pipeline on
                # that mount.
                found_new_or_modified = False
                for dirpath, dirnames, filenames in os.walk(root):
                    for filename in filenames:
                        path = os.path.join(dirpath, filename)
                        if path not in self._paths:
                            logger.debug("Found new asset: %s" % path)
                            self._paths.add(path)
                            found_new_or_modified = True
                            break
                        if os.path.getmtime(path) > self._last_bake:
                            logger.debug("Found modified asset: %s" % path)
                            found_new_or_modified = True
                            break

                    if found_new_or_modified:
                        break

                if found_new_or_modified:
                    self._runPipeline(root)

            time.sleep(self.interval)

    def _runPipeline(self, root):
        self._last_bake = time.time()
        try:
            self._record = self.pipeline.run(
                    root,
                    previous_record=self._record,
                    save_record=False)
        except:
            pass

