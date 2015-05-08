import logging
from piecrust.commands.base import ChefCommand
from piecrust.serving.wrappers import run_werkzeug_server, run_gunicorn_server


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
        root_dir = ctx.app.root_dir
        host = ctx.args.address
        port = int(ctx.args.port)
        debug = ctx.args.debug or ctx.args.use_debugger

        if ctx.args.wsgi == 'werkzeug':
            run_werkzeug_server(
                    root_dir, host, port,
                    debug_piecrust=debug,
                    sub_cache_dir=ctx.app.sub_cache_dir,
                    use_debugger=debug,
                    use_reloader=ctx.args.use_reloader)

        elif ctx.args.wsgi == 'gunicorn':
            options = {
                    'bind': '%s:%s' % (host, port),
                    'accesslog': '-',  # print access log to stderr
                    }
            if debug:
                options['loglevel'] = 'debug'
            if ctx.args.use_reloader:
                options['reload'] = True
            run_gunicorn_server(
                    root_dir,
                    debug_piecrust=debug,
                    sub_cache_dir=ctx.app.sub_cache_dir,
                    gunicorn_options=options)

