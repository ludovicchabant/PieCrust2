import logging
from piecrust.commands.base import ChefCommand
from piecrust.publishing.publisher import Publisher


logger = logging.getLogger(__name__)


class PublishCommand(ChefCommand):
    """ Command for running publish targets for the current site.
    """
    def __init__(self):
        super(PublishCommand, self).__init__()
        self.name = 'publish'
        self.description = "Publishes you website to a specific target."

    def setupParser(self, parser, app):
        parser.add_argument(
                '-l', '--list',
                action='store_true',
                help="List available publish targets for the current site.")
        parser.add_argument(
                '--log-publisher',
                metavar='LOG_FILE',
                help="Log the publisher's output to a given file.")
        parser.add_argument(
                'target',
                nargs='?',
                default='default',
                help="The publish target to use.")

    def run(self, ctx):
        if ctx.args.list:
            pub_cfg = ctx.app.config.get('publish')
            if not pub_cfg:
                logger.info("No available publish targets.")
                return

            for name, cfg in pub_cfg.items():
                desc = cfg.get('description')
                if not desc:
                    logger.info(name)
                else:
                    logger.info("%s: %s" % (name, desc))
            return

        pub = Publisher(ctx.app)
        pub.run(ctx.args.target, log_file=ctx.args.log_publisher)

