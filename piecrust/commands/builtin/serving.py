import logging
from piecrust.serving import Server, _sse_abort
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class ServeCommand(ChefCommand):
    def __init__(self):
        super(ServeCommand, self).__init__()
        self.name = 'serve'
        self.description = "Runs a local web server to serve your website."
        self.cache_name = 'server'

    def setupParser(self, parser, app):
        parser.add_argument(
                '-p', '--port',
                help="The port for the web server",
                default=8080)
        parser.add_argument(
                '-a', '--address',
                help="The host for the web server",
                default='localhost')
        parser.add_argument(
                '--use-reloader',
                help="Restart the server when PieCrust code changes",
                action='store_true')
        parser.add_argument(
                '--use-debugger',
                help="Show the debugger when an error occurs",
                action='store_true')
        parser.add_argument(
                '--wsgi',
                help="The WSGI server implementation to use",
                choices=['werkzeug', 'gunicorn'],
                default='werkzeug')

    def run(self, ctx):
        host = ctx.args.address
        port = int(ctx.args.port)
        debug = ctx.args.debug or ctx.args.use_debugger

        server = Server(
                ctx.app.root_dir,
                debug=debug,
                sub_cache_dir=ctx.app.sub_cache_dir,
                use_reloader=ctx.args.use_reloader)
        app = server.getWsgiApp()

        if ctx.args.wsgi == 'werkzeug':
            from werkzeug.serving import run_simple
            try:
                run_simple(host, port, app,
                           threaded=True,
                           use_debugger=debug,
                           use_reloader=ctx.args.use_reloader)
            finally:
                _sse_abort.set()

        elif ctx.args.wsgi == 'gunicorn':
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

            options = {
                    'bind': '%s:%s' % (host, port),
                    'accesslog': '-',
                    'worker_class': 'gaiohttp',
                    'workers': 2,
                    'timeout': 999999}
            if debug:
                options['loglevel'] = 'debug'
            if ctx.args.use_reloader:
                options['reload'] = True
            app_wrapper = PieCrustGunicornApplication(app, options)
            app_wrapper.run()

