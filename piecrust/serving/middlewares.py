import os.path
from werkzeug.exceptions import HTTPException, NotFound, Forbidden
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import ClosingIterator
from piecrust import RESOURCES_DIR, CACHE_DIR
from piecrust.data.builder import (
    DataBuildingContext, build_page_data)
from piecrust.data.debug import build_var_debug_info
from piecrust.page import PageNotFoundError
from piecrust.routing import RouteNotFoundError
from piecrust.serving.util import (
    make_wrapped_file_response, get_requested_page, get_app_for_server)


class PieCrustStaticResourcesMiddleware(object):
    """ WSGI middleware that serves static files from the `resources/server`
        directory in the PieCrust package.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        static_mount = '/__piecrust_static/'

        request = Request(environ)
        if request.path.startswith(static_mount):
            rel_req_path = request.path[len(static_mount):]
            mount = os.path.join(RESOURCES_DIR, 'server')
            full_path = os.path.join(mount, rel_req_path)
            try:
                response = make_wrapped_file_response(
                    environ, request, full_path)
                return response(environ, start_response)
            except OSError:
                pass

        return self.app(environ, start_response)


class PieCrustDebugMiddleware(object):
    """ WSGI middleware that handles debugging of PieCrust stuff, and runs
        the asset pipeline in an SSE thread.
    """
    def __init__(self, app, appfactory,
                 run_sse_check=None):
        self.app = app
        self.appfactory = appfactory
        self.run_sse_check = run_sse_check
        self._proc_loop = None
        self._out_dir = os.path.join(
            appfactory.root_dir, CACHE_DIR, appfactory.cache_key, 'server')
        self._handlers = {
            'debug_info': self._getDebugInfo,
            'werkzeug_shutdown': self._shutdownWerkzeug,
            'pipeline_status': self._startSSEProvider}

        if not self.run_sse_check or self.run_sse_check():
            # When using a server with code reloading, some implementations
            # use process forking and we end up going here twice. We only want
            # to start the pipeline loop in the inner process most of the
            # time so we let the implementation tell us if this is OK.
            from piecrust.serving.procloop import ProcessingLoop
            self._proc_loop = ProcessingLoop(self.appfactory, self._out_dir)
            self._proc_loop.start()

    def __call__(self, environ, start_response):
        debug_mount = '/__piecrust_debug/'

        request = Request(environ)
        if request.path.startswith(debug_mount):
            rel_req_path = request.path[len(debug_mount):]
            handler = self._handlers.get(rel_req_path)
            if handler is not None:
                try:
                    return handler(request, start_response)
                except HTTPException as ex:
                    return ex(environ, start_response)

        return self.app(environ, start_response)

    def _getDebugInfo(self, request, start_response):
        app = get_app_for_server(self.appfactory)
        if not app.config.get('site/enable_debug_info', True):
            raise Forbidden("PieCrust debug info isn't enabled.")

        found = False
        page_path = request.args.get('page')
        try:
            req_page = get_requested_page(app, page_path)
            found = (req_page is not None)
        except (RouteNotFoundError, PageNotFoundError):
            pass
        if not found:
            raise NotFound("No such page: %s" % page_path)

        ctx = DataBuildingContext(req_page.page,
                                  sub_num=req_page.sub_num)
        data = build_page_data(ctx)

        var_path = request.args.getlist('var')
        if not var_path:
            var_path = None
        output = build_var_debug_info(data, var_path)

        response = Response(output, mimetype='text/html')
        return response(request.environ, start_response)

    def _shutdownWerkzeug(self, request, start_response):
        shutdown_func = request.environ.get('werkzeug.server.shutdown')
        if shutdown_func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        shutdown_func()
        response = Response("Server shutting down...")
        return response(request.environ, start_response)

    def _startSSEProvider(self, request, start_response):
        from piecrust.serving.procloop import (
            PipelineStatusServerSentEventProducer)
        provider = PipelineStatusServerSentEventProducer(
            self._proc_loop)
        it = provider.run()
        response = Response(it, mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Last-Event-ID'] = \
            self._proc_loop.last_status_id
        return ClosingIterator(
            response(request.environ, start_response),
            [provider.close])

