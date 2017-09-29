import logging
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
            '--admin',
            help="Also serve the administration panel.",
            action='store_true')
        parser.add_argument(
            '--wsgi',
            help="The WSGI server implementation to use",
            choices=['werkzeug', 'gunicorn'],
            default='werkzeug')

    def run(self, ctx):
        appfactory = ctx.appfactory
        host = ctx.args.address
        port = int(ctx.args.port)
        use_debugger = ctx.args.debug or ctx.args.use_debugger

        from piecrust.serving.wrappers import run_piecrust_server
        run_piecrust_server(
            ctx.args.wsgi, appfactory, host, port,
            is_cmdline_mode=True,
            serve_admin=ctx.args.admin,
            use_reloader=ctx.args.use_reloader,
            use_debugger=use_debugger)
