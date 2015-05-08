import os
from piecrust.serving.server import Server
from piecrust.serving.procloop import _sse_abort


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
    try:
        run_simple(host, port, app,
                   threaded=True,
                   use_debugger=use_debugger,
                   use_reloader=use_reloader)
    finally:
        _sse_abort.set()


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


def _get_piecrust_server(root_dir, **kwargs):
    server = Server(root_dir, **kwargs)
    app = server.getWsgiApp()
    return app

