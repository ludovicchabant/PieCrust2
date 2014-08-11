import logging
from piecrust.serving import Server
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class ServeCommand(ChefCommand):
    def __init__(self):
        super(ServeCommand, self).__init__()
        self.name = 'serve'
        self.description = "Runs a local web server to serve your website."

    def setupParser(self, parser, app):
        parser.add_argument('-p', '--port',
                help="The port for the web server",
                default=8080)
        parser.add_argument('-a', '--address',
                help="The host for the web server",
                default='localhost')

    def run(self, ctx):
        server = Server(
                ctx.app.root_dir,
                host=ctx.args.address,
                port=ctx.args.port,
                debug=ctx.args.debug)
        server.run()

