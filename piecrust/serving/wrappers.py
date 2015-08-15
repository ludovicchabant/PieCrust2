import os
import signal
import logging
import threading
import urllib.request


logger = logging.getLogger(__name__)


def run_werkzeug_server(root_dir, host, port,
                        debug_piecrust=False, sub_cache_dir=None,
                        use_debugger=False, use_reloader=False):
    from werkzeug.serving import run_simple

    def _run_sse_check():
        # We don't want to run the processing loop here if this isn't
        # the actual process that does the serving. In most cases it is,
        # but if we're using Werkzeug's reloader, then it won't be the
        # first time we get there... it will only be the correct process
        # the second time, when the reloading process is spawned, with the
        # `WERKZEUG_RUN_MAIN` variable set.
        return (not use_reloader or
                os.environ.get('WERKZEUG_RUN_MAIN') == 'true')

    app = _get_piecrust_server(root_dir,
                               debug=debug_piecrust,
                               sub_cache_dir=sub_cache_dir,
                               run_sse_check=_run_sse_check)

    # We need to do a few things to get Werkzeug to properly shutdown or
    # restart while SSE responses are running. This is because Werkzeug runs
    # them in background threads (because we tell it to), but those threads
    # are not marked as "daemon", so when the main thread tries to exit, it
    # will wait on those SSE responses to end, which will pretty much never
    # happen (except for a timeout or the user closing their browser).
    #
    # In theory we should be using a proper async server for this kind of
    # stuff, but I'd rather avoid additional dependencies on stuff that's not
    # necessarily super portable.
    #
    # Anyway, we run the server as usual, but we intercept the `SIGINT`
    # signal for when the user presses `CTRL-C`. When that happens, we set a
    # flag that will make all existing SSE loops return, which will make it
    # possible for the main thread to end too.
    #
    # We also need to do a few thing for the "reloading" feature in Werkzeug,
    # see the comment down there for more info.
    def _shutdown_server():
        from piecrust.serving import procloop
        procloop.server_shutdown = True

    def _shutdown_server_and_raise_sigint():
        if not use_reloader or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            # We only need to shutdown the SSE requests for the process
            # that actually runs them.
            print("")
            print("Shutting server down...")
            _shutdown_server()
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT,
                  lambda *args: _shutdown_server_and_raise_sigint())

    try:
        run_simple(host, port, app,
                   threaded=True,
                   use_debugger=use_debugger,
                   use_reloader=use_reloader)
    except SystemExit:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            # When using the reloader, if code has changed, the child process
            # will use `sys.exit` to end and let the master process restart
            # it... we need to shutdown the SSE requests otherwise it will
            # not exit.
            _shutdown_server()
        raise


def run_gunicorn_server(root_dir,
                        debug_piecrust=False, sub_cache_dir=None,
                        gunicorn_options=None):
    from gunicorn.app.base import BaseApplication

    class PieCrustGunicornApplication(BaseApplication):
        def __init__(self, app, options):
            self.app = app
            self.options = options
            super(PieCrustGunicornApplication, self).__init__()

        def load_config(self):
            for k, v in self.options.items():
                if k in self.cfg.settings and v is not None:
                    self.cfg.set(k, v)

        def load(self):
            return self.app

    app = _get_piecrust_server(root_dir,
                               debug=debug_piecrust,
                               sub_cache_dir=sub_cache_dir)

    gunicorn_options = gunicorn_options or {}
    app_wrapper = PieCrustGunicornApplication(app, gunicorn_options)
    app_wrapper.run()


def _get_piecrust_server(root_dir, debug=False, sub_cache_dir=None,
                         run_sse_check=None):
    from piecrust.serving.middlewares import (
            StaticResourcesMiddleware, PieCrustDebugMiddleware)
    from piecrust.serving.server import WsgiServer
    app = WsgiServer(root_dir, debug=debug, sub_cache_dir=sub_cache_dir)
    app = StaticResourcesMiddleware(app)
    app = PieCrustDebugMiddleware(app, root_dir,
                                  sub_cache_dir=sub_cache_dir,
                                  run_sse_check=run_sse_check)
    return app

