import io
import os
import re
import gzip
import time
import os.path
import hashlib
import logging
import datetime
from werkzeug.exceptions import (
        NotFound, MethodNotAllowed, InternalServerError, HTTPException)
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import ClosingIterator, wrap_file
from jinja2 import FileSystemLoader, Environment
from piecrust import CACHE_DIR, RESOURCES_DIR
from piecrust.app import PieCrust
from piecrust.rendering import QualifiedPage, PageRenderingContext, render_page
from piecrust.sources.base import MODE_PARSING
from piecrust.uriutil import split_sub_uri


logger = logging.getLogger(__name__)


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


class WsgiServerWrapper(object):
    def __init__(self, server):
        self.server = server

    def __call__(self, environ, start_response):
        return self.server._run_request(environ, start_response)


class MultipleNotFound(HTTPException):
    code = 404

    def __init__(self, description, nfes):
        super(MultipleNotFound, self).__init__(description)
        self._nfes = nfes

    def get_description(self, environ=None):
        from werkzeug.utils import escape
        desc = '<p>' + self.description + '</p>'
        desc += '<p>'
        for nfe in self._nfes:
            desc += '<li>' + escape(nfe.description) + '</li>'
        desc += '</p>'
        return desc


class Server(object):
    def __init__(self, root_dir,
                 debug=False, sub_cache_dir=None, enable_debug_info=True,
                 static_preview=True, run_sse_check=None):
        self.root_dir = root_dir
        self.debug = debug
        self.sub_cache_dir = sub_cache_dir
        self.enable_debug_info = enable_debug_info
        self.run_sse_check = run_sse_check
        self.static_preview = static_preview
        self._page_record = ServeRecord()
        self._out_dir = os.path.join(root_dir, CACHE_DIR, 'server')
        self._proc_loop = None
        self._mimetype_map = load_mimetype_map()

    def getWsgiApp(self):
        # Bake all the assets so we know what we have, and so we can serve
        # them to the client. We need a temp app for this.
        app = PieCrust(root_dir=self.root_dir, debug=self.debug)
        if self.sub_cache_dir:
            app._useSubCacheDir(self.sub_cache_dir)
        self._out_dir = os.path.join(app.sub_cache_dir, 'server')

        if not self.run_sse_check or self.run_sse_check():
            # When using a server with code reloading, some implementations
            # use process forking and we end up going here twice. We only want
            # to start the pipeline loop in the inner process most of the
            # time so we let the implementation tell us if this is OK.
            from piecrust.processing.pipeline import ProcessorPipeline
            from piecrust.serving.procloop import ProcessingLoop
            pipeline = ProcessorPipeline(app, self._out_dir)
            self._proc_loop = ProcessingLoop(pipeline)
            self._proc_loop.start()

        # Run the WSGI app.
        wsgi_wrapper = WsgiServerWrapper(self)
        return wsgi_wrapper

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
            logger.error("Only GET requests are allowed, got %s" %
                         request.method)
            raise MethodNotAllowed()

        # Handle special requests right away.
        response = self._try_special_request(environ, request)
        if response is not None:
            return response(environ, start_response)

        # Also handle requests to a pipeline-built asset right away.
        response = self._try_serve_asset(environ, request)
        if response is not None:
            return response(environ, start_response)

        # Create the app for this request.
        app = PieCrust(root_dir=self.root_dir, debug=self.debug)
        if self.sub_cache_dir:
            app._useSubCacheDir(self.sub_cache_dir)
        app.config.set('site/root', '/')
        app.config.set('server/is_serving', True)
        if (app.config.get('site/enable_debug_info') and
                self.enable_debug_info and
                '!debug' in request.args):
            app.config.set('site/show_debug_info', True)

        # We'll serve page assets directly from where they are.
        app.env.base_asset_url_format = '/_asset/%path%'

        # Let's see if it can be a page asset.
        response = self._try_serve_page_asset(app, environ, request)
        if response is not None:
            return response(environ, start_response)

        # Nope. Let's see if it's an actual page.
        try:
            response = self._try_serve_page(app, environ, request)
            return response(environ, start_response)
        except (RouteNotFoundError, SourceNotFoundError) as ex:
            raise NotFound() from ex
        except HTTPException:
            raise
        except Exception as ex:
            if app.debug:
                logger.exception(ex)
                raise
            msg = str(ex)
            logger.error(msg)
            raise InternalServerError(msg) from ex

    def _try_special_request(self, environ, request):
        static_mount = '/__piecrust_static/'
        if request.path.startswith(static_mount):
            rel_req_path = request.path[len(static_mount):]
            mount = os.path.join(RESOURCES_DIR, 'server')
            full_path = os.path.join(mount, rel_req_path)
            try:
                response = self._make_wrapped_file_response(
                        environ, request, full_path)
                return response
            except OSError:
                pass

        debug_mount = '/__piecrust_debug/'
        if request.path.startswith(debug_mount):
            rel_req_path = request.path[len(debug_mount):]
            if rel_req_path == 'pipeline_status':
                from piecrust.serving.procloop import (
                        PipelineStatusServerSideEventProducer)
                provider = PipelineStatusServerSideEventProducer(
                        self._proc_loop.status_queue)
                it = ClosingIterator(provider.run(), [provider.close])
                response = Response(it)
                response.headers['Cache-Control'] = 'no-cache'
                if 'text/event-stream' in request.accept_mimetypes:
                    response.mimetype = 'text/event-stream'
                response.direct_passthrough = True
                response.implicit_sequence_conversion = False
                return response

        return None

    def _try_serve_asset(self, environ, request):
        rel_req_path = request.path.lstrip('/').replace('/', os.sep)
        if request.path.startswith('/_cache/'):
            # Some stuff needs to be served directly from the cache directory,
            # like LESS CSS map files.
            full_path = os.path.join(self.root_dir, rel_req_path)
        else:
            full_path = os.path.join(self._out_dir, rel_req_path)

        try:
            response = self._make_wrapped_file_response(
                    environ, request, full_path)
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

        return self._make_wrapped_file_response(environ, request, full_path)

    def _try_serve_page(self, app, environ, request):
        # Try to find what matches the requested URL.
        req_path, page_num = split_sub_uri(app, request.path)

        routes = find_routes(app.routes, req_path)
        if len(routes) == 0:
            raise RouteNotFoundError("Can't find route for: %s" % req_path)

        rendered_page = None
        not_found_errors = []
        for route, route_metadata in routes:
            try:
                logger.debug("Trying to render match from source '%s'." %
                             route.source_name)
                rendered_page = self._try_render_page(
                        app, route, route_metadata, page_num, req_path)
                if rendered_page is not None:
                    break
            except NotFound as nfe:
                not_found_errors.append(nfe)

        # If we haven't found any good match, raise whatever exception we
        # first got. Otherwise, raise a generic exception.
        if rendered_page is None:
            msg = ("Can't find path for '%s', looked in sources: %s" %
                   (req_path,
                    ', '.join([r.source_name for r, _ in routes])))
            raise MultipleNotFound(msg, not_found_errors)

        # Start doing stuff.
        page = rendered_page.page
        rp_content = rendered_page.content

        # Profiling.
        if app.config.get('site/show_debug_info'):
            now_time = time.clock()
            timing_info = (
                    '%8.1f ms' %
                    ((now_time - app.env.start_time) * 1000.0))
            rp_content = rp_content.replace(
                    '__PIECRUST_TIMING_INFORMATION__', timing_info)

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

    def _try_render_page(self, app, route, route_metadata, page_num, req_path):
        # Match the route to an actual factory.
        taxonomy_info = None
        source = app.getSource(route.source_name)
        if route.taxonomy_name is None:
            factory = source.findPageFactory(route_metadata, MODE_PARSING)
            if factory is None:
                raise NotFound("No path found for '%s' in source '%s'." %
                               (req_path, source.name))
        else:
            taxonomy = app.getTaxonomy(route.taxonomy_name)
            tax_terms = route.getTaxonomyTerms(route_metadata)
            taxonomy_info = (taxonomy, tax_terms)

            tax_page_ref = taxonomy.getPageRef(source)
            factory = tax_page_ref.getFactory()

        # Build the page.
        page = factory.buildPage()
        # We force the rendering of the page because it could not have
        # changed, but include pages that did change.
        qp = QualifiedPage(page, route, route_metadata)
        render_ctx = PageRenderingContext(qp,
                                          page_num=page_num,
                                          force_render=True)
        if taxonomy_info is not None:
            _, tax_terms = taxonomy_info
            render_ctx.setTaxonomyFilter(tax_terms)

        # See if this page is known to use sources. If that's the case,
        # just don't use cached rendered segments for that page (but still
        # use them for pages that are included in it).
        uri = qp.getUri()
        entry = self._page_record.getEntry(uri, page_num)
        if (taxonomy_info is not None or entry is None or
                entry.used_source_names):
            cache_key = '%s:%s' % (uri, page_num)
            app.env.rendered_segments_repository.invalidate(cache_key)

        # Render the page.
        rendered_page = render_page(render_ctx)

        # Check if this page is a taxonomy page that actually doesn't match
        # anything.
        if taxonomy_info is not None:
            paginator = rendered_page.data.get('pagination')
            if (paginator and paginator.is_loaded and
                    len(paginator.items) == 0):
                taxonomy = taxonomy_info[0]
                message = ("This URL matched a route for taxonomy '%s' but "
                           "no pages have been found to have it. This page "
                           "won't be generated by a bake." % taxonomy.name)
                raise NotFound(message)

        # Remember stuff for next time.
        if entry is None:
            entry = ServeRecordPageEntry(req_path, page_num)
            self._page_record.addEntry(entry)
        for p, pinfo in render_ctx.render_passes.items():
            entry.used_source_names |= pinfo.used_source_names

        # Ok all good.
        return rendered_page

    def _make_wrapped_file_response(self, environ, request, path):
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
        response.mimetype = self._mimetype_map.get(
                ext.lstrip('.'), 'text/plain')
        return response

    def _handle_error(self, exception, environ, start_response):
        code = 500
        if isinstance(exception, HTTPException):
            code = exception.code

        path = 'error'
        if isinstance(exception, (NotFound, MultipleNotFound)):
            path += '404'

        descriptions = self._get_exception_descriptions(exception)

        env = Environment(loader=ErrorMessageLoader())
        template = env.get_template(path)
        context = {'details': descriptions}
        response = Response(template.render(context), mimetype='text/html')
        response.status_code = code
        return response(environ, start_response)

    def _get_exception_descriptions(self, exception):
        desc = []
        while exception is not None:
            if isinstance(exception, MultipleNotFound):
                desc += [e.description for e in exception._nfes]
            elif isinstance(exception, HTTPException):
                desc.append(exception.description)
            else:
                desc.append(str(exception))

            inner_ex = exception.__cause__
            if inner_ex is None:
                inner_ex = exception.__context__
            exception = inner_ex
        return desc


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
        'atom': 'application/atom+xml',  # or 'text/xml'?
        'rss': 'application/rss+xml',    # or 'text/xml'?
        'json': 'application/json'}


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


class ErrorMessageLoader(FileSystemLoader):
    def __init__(self):
        base_dir = os.path.join(RESOURCES_DIR, 'messages')
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

