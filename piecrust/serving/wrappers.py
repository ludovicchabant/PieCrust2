import os
import signal
import logging


logger = logging.getLogger(__name__)


def run_piecrust_server(wsgi, appfactory, host, port,
                        is_cmdline_mode=False,
                        serve_admin=False,
                        use_debugger=False,
                        use_reloader=False):

    if wsgi == 'werkzeug':
        _run_werkzeug_server(appfactory, host, port,
                             is_cmdline_mode=is_cmdline_mode,
                             serve_admin=serve_admin,
                             use_debugger=use_debugger,
                             use_reloader=use_reloader)

    elif wsgi == 'gunicorn':
        options = {
            'bind': '%s:%s' % (host, port),
            'accesslog': '-',  # print access log to stderr
        }
        if use_debugger:
            options['loglevel'] = 'debug'
        if use_reloader:
            options['reload'] = True
        _run_gunicorn_server(appfactory,
                             is_cmdline_mode=is_cmdline_mode,
                             gunicorn_options=options)

    else:
        raise Exception("Unknown WSGI server: %s" % wsgi)


def _run_werkzeug_server(appfactory, host, port, *,
                         is_cmdline_mode=False,
                         serve_admin=False,
                         use_debugger=False,
                         use_reloader=False):
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

    app = _get_piecrust_server(appfactory,
                               is_cmdline_mode=is_cmdline_mode,
                               serve_site=True,
                               serve_admin=serve_admin,
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

        if serve_admin:
            from piecrust.admin import pubutil
            pubutil.server_shutdown = True

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

    # Disable debugger PIN protection.
    os.environ['WERKZEUG_DEBUG_PIN'] = 'off'

    if is_cmdline_mode and serve_admin:
        admin_url = 'http://%s:%s%s' % (host, port, '/pc-admin')
        logger.info("The administrative panel is available at: %s" %
                    admin_url)

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


def _run_gunicorn_server(appfactory,
                         is_cmdline_mode=False,
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

    app = _get_piecrust_server(appfactory,
                               is_cmdline_mode=is_cmdline_mode)

    gunicorn_options = gunicorn_options or {}
    app_wrapper = PieCrustGunicornApplication(app, gunicorn_options)
    app_wrapper.run()


def get_piecrust_server(root_dir, *,
                        debug=False,
                        cache_key=None,
                        serve_site=True,
                        serve_admin=False,
                        is_cmdline_mode=False):
    from piecrust.app import PieCrustFactory
    appfactory = PieCrustFactory(root_dir,
                                 debug=debug,
                                 cache_key=cache_key)
    return _get_piecrust_server(appfactory,
                                serve_site=serve_site,
                                serve_admin=serve_admin,
                                is_cmdline_mode=is_cmdline_mode)


def _get_piecrust_server(appfactory, *,
                         serve_site=True,
                         serve_admin=False,
                         is_cmdline_mode=False,
                         run_sse_check=None):
    app = None

    if serve_site:
        from piecrust.serving.middlewares import (
            PieCrustStaticResourcesMiddleware, PieCrustDebugMiddleware)
        from piecrust.serving.server import PieCrustServer

        app = PieCrustServer(appfactory)
        app = PieCrustStaticResourcesMiddleware(app)

        if is_cmdline_mode:
            app = PieCrustDebugMiddleware(
                app, appfactory, run_sse_check=run_sse_check)

    if serve_admin:
        from piecrust.admin.web import create_foodtruck_app

        admin_root_url = ('/pc-admin' if is_cmdline_mode else None)

        es = {
            'FOODTRUCK_CMDLINE_MODE': is_cmdline_mode,
            'FOODTRUCK_ROOT_DIR': appfactory.root_dir,
            'FOODTRUCK_ROOT_URL': admin_root_url,
            'DEBUG': appfactory.debug}
        if is_cmdline_mode:
            es.update({
                'SECRET_KEY': os.urandom(22),
                'LOGIN_DISABLED': True})

        if appfactory.debug and is_cmdline_mode:
            # Disable PIN protection with Werkzeug's debugger.
            os.environ['WERKZEUG_DEBUG_PIN'] = 'off'

        admin_app = create_foodtruck_app(es, url_prefix=admin_root_url)
        if app is not None:
            admin_app.wsgi_app = _PieCrustSiteOrAdminMiddleware(
                app, admin_app.wsgi_app, admin_root_url)

        app = admin_app

    return app


class _PieCrustSiteOrAdminMiddleware:
    def __init__(self, main_app, admin_app, admin_root_url):
        from werkzeug.exceptions import abort

        def _err_resp(e, sr):
            abort(404)

        self.main_app = main_app
        self.admin_app = admin_app or _err_resp
        self.admin_root_url = admin_root_url

    def __call__(self, environ, start_response):
        path_info = environ.get('PATH_INFO', '')
        if path_info.startswith(self.admin_root_url):
            return self.admin_app(environ, start_response)
        return self.main_app(environ, start_response)


class _PieCrustAdminScriptNamePatcherMiddleware:
    def __init__(self, admin_app, admin_root_url):
        self.admin_app = admin_app
        self.admin_root_url = '/%s' % admin_root_url.strip('/')

    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = self.admin_root_url
        return self.admin_app(environ, start_response)
