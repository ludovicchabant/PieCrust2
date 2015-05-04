import io
import os
import re
import json
import gzip
import time
import queue
import os.path
import hashlib
import logging
import datetime
import threading
from werkzeug.exceptions import (
        NotFound, MethodNotAllowed, InternalServerError, HTTPException)
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import ClosingIterator, wrap_file
from jinja2 import FileSystemLoader, Environment
from piecrust.app import PieCrust
from piecrust.environment import StandardEnvironment
from piecrust.processing.base import ProcessorPipeline
from piecrust.rendering import QualifiedPage, PageRenderingContext, render_page
from piecrust.sources.base import PageFactory, MODE_PARSING
from piecrust.uriutil import split_sub_uri


logger = logging.getLogger(__name__)


_sse_abort = threading.Event()


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


class WsgiServerWrapper(object):
    def __init__(self, server):
        self.server = server

    def __call__(self, environ, start_response):
        return self.server._run_request(environ, start_response)


class Server(object):
    def __init__(self, root_dir,
                 debug=False, sub_cache_dir=None,
                 use_reloader=False, static_preview=True):
        self.root_dir = root_dir
        self.debug = debug
        self.sub_cache_dir = sub_cache_dir
        self.use_reloader = use_reloader
        self.static_preview = static_preview
        self._out_dir = None
        self._page_record = None
        self._proc_loop = None
        self._mimetype_map = load_mimetype_map()

    def getWsgiApp(self):
        # Bake all the assets so we know what we have, and so we can serve
        # them to the client. We need a temp app for this.
        app = PieCrust(root_dir=self.root_dir, debug=self.debug)
        app._useSubCacheDir(self.sub_cache_dir)
        self._out_dir = os.path.join(app.sub_cache_dir, 'server')
        self._page_record = ServeRecord()

        if (not self.use_reloader or
                os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
            # We don't want to run the processing loop here if this isn't
            # the actual process that does the serving. In most cases it is,
            # but if we're using Werkzeug's reloader, then it won't be the
            # first time we get there... it will only be the correct process
            # the second time, when the reloading process is spawned, with the
            # `WERKZEUG_RUN_MAIN` variable set.
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
        app._useSubCacheDir(self.sub_cache_dir)
        app.config.set('site/root', '/')
        app.config.set('server/is_serving', True)
        if (app.config.get('site/enable_debug_info') and
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
            raise NotFound(str(ex)) from ex
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
            mount = os.path.join(
                    os.path.dirname(__file__),
                    'resources', 'server')
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
        first_not_found = None
        for route, route_metadata in routes:
            try:
                logger.debug("Trying to render match from source '%s'." %
                             route.source_name)
                rendered_page = self._try_render_page(
                        app, route, route_metadata, page_num, req_path)
                if rendered_page is not None:
                    break
            except NotFound as nfe:
                if first_not_found is None:
                    first_not_found = nfe
        else:
            raise SourceNotFoundError(
                    "Can't find path for: %s (looked in: %s)" %
                    (req_path, [r.source_name for r, _ in routes]))

        # If we haven't found any good match, raise whatever exception we
        # first got. Otherwise, raise a generic exception.
        if rendered_page is None:
            first_not_found = first_not_found or NotFound(
                    "This page couldn't be found.")
            raise first_not_found

        # Start doing stuff.
        page = rendered_page.page
        rp_content = rendered_page.content

        # Profiling.
        if app.config.get('site/show_debug_info'):
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

    def _try_render_page(self, app, route, route_metadata, page_num, req_path):
        # Match the route to an actual factory.
        taxonomy_info = None
        source = app.getSource(route.source_name)
        if route.taxonomy_name is None:
            factory = source.findPageFactory(route_metadata, MODE_PARSING)
            if factory is None:
                return None
        else:
            taxonomy = app.getTaxonomy(route.taxonomy_name)
            route_terms = route_metadata.get(taxonomy.term_name)
            if route_terms is None:
                return None

            tax_page_ref = taxonomy.getPageRef(source.name)
            factory = tax_page_ref.getFactory()
            tax_terms = route.unslugifyTaxonomyTerm(route_terms)
            route_metadata[taxonomy.term_name] = tax_terms
            taxonomy_info = (taxonomy, tax_terms)

        # Build the page.
        page = factory.buildPage()
        # We force the rendering of the page because it could not have
        # changed, but include pages that did change.
        qp = QualifiedPage(page, route, route_metadata)
        render_ctx = PageRenderingContext(qp,
                                          page_num=page_num,
                                          force_render=True)
        if taxonomy_info is not None:
            taxonomy, tax_terms = taxonomy_info
            render_ctx.setTaxonomyFilter(taxonomy, tax_terms)

        # See if this page is known to use sources. If that's the case,
        # just don't use cached rendered segments for that page (but still
        # use them for pages that are included in it).
        uri = qp.getUri()
        assert uri == req_path
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
        if isinstance(exception, NotFound):
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
            if isinstance(exception, HTTPException):
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
    for route in routes:
        metadata = route.matchUri(uri)
        if metadata is not None:
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


class PipelineStatusServerSideEventProducer(object):
    def __init__(self, status_queue):
        self.status_queue = status_queue
        self.interval = 2
        self.timeout = 60*10
        self._start_time = 0

    def run(self):
        logger.debug("Starting pipeline status SSE.")
        self._start_time = time.time()

        outstr = 'event: ping\ndata: started\n\n'
        yield bytes(outstr, 'utf8')

        count = 0
        while True:
            if time.time() > self.timeout + self._start_time:
                logger.debug("Closing pipeline status SSE, timeout reached.")
                outstr = 'event: pipeline_timeout\ndata: bye\n\n'
                yield bytes(outstr, 'utf8')
                break

            if _sse_abort.is_set():
                break

            try:
                logger.debug("Polling pipeline status queue...")
                count += 1
                data = self.status_queue.get(True, self.interval)
            except queue.Empty:
                if count < 3:
                    continue
                data = {'type': 'ping', 'message': 'ping'}
                count = 0

            event_type = data['type']
            outstr = 'event: %s\ndata: %s\n\n' % (
                    event_type, json.dumps(data))
            logger.debug("Sending pipeline status SSE.")
            yield bytes(outstr, 'utf8')

    def close(self):
        logger.debug("Closing pipeline status SSE.")


class ProcessingLoop(threading.Thread):
    def __init__(self, pipeline):
        super(ProcessingLoop, self).__init__(
                name='pipeline-reloader', daemon=True)
        self.pipeline = pipeline
        self.status_queue = queue.Queue()
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

            # Update the status queue.
            # (we need to clear it because there may not be a consumer
            #  on the other side, if the user isn't running with the
            #  debug window active)
            while True:
                try:
                    self.status_queue.get_nowait()
                except queue.Empty:
                    break

            if self._record.success:
                item = {
                        'type': 'pipeline_success'}
                self.status_queue.put_nowait(item)
            else:
                item = {
                        'type': 'pipeline_error',
                        'assets': []}
                for entry in self._record.entries:
                    if entry.errors:
                        asset_item = {
                                'path': entry.rel_input,
                                'errors': list(entry.errors)}
                        item['assets'].append(asset_item)
                self.status_queue.put_nowait(item)
        except:
            pass

