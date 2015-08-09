import os.path
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import ClosingIterator
from piecrust import RESOURCES_DIR, CACHE_DIR
from piecrust.serving.util import make_wrapped_file_response


class StaticResourcesMiddleware(object):
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
    """ WSGI middleware that handles debugging of PieCrust stuff.
    """
    def __init__(self, app, root_dir, debug=False,
                 sub_cache_dir=None, run_sse_check=None):
        self.app = app
        self.root_dir = root_dir
        self.debug = debug
        self.run_sse_check = run_sse_check
        self._proc_loop = None
        self._out_dir = os.path.join(root_dir, CACHE_DIR, 'server')
        if sub_cache_dir:
            self._out_dir = os.path.join(sub_cache_dir, 'server')
        self._handlers = {
                'werkzeug_shutdown': self._shutdownWerkzeug,
                'pipeline_status': self._startSSEProvider}

        if not self.run_sse_check or self.run_sse_check():
            # When using a server with code reloading, some implementations
            # use process forking and we end up going here twice. We only want
            # to start the pipeline loop in the inner process most of the
            # time so we let the implementation tell us if this is OK.
            from piecrust.serving.procloop import ProcessingLoop
            self._proc_loop = ProcessingLoop(root_dir, self._out_dir,
                                             sub_cache_dir=sub_cache_dir,
                                             debug=debug)
            self._proc_loop.start()

    def __call__(self, environ, start_response):
        debug_mount = '/__piecrust_debug/'

        request = Request(environ)
        if request.path.startswith(debug_mount):
            rel_req_path = request.path[len(debug_mount):]
            handler = self._handlers.get(rel_req_path)
            if handler is not None:
                return handler(request, start_response)

        return self.app(environ, start_response)

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

