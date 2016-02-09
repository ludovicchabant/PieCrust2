import logging
import urllib.parse
from piecrust.commands.base import ChefCommand
from piecrust.publishing.publisher import Publisher, find_publisher_name


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
                '--preview',
                action='store_true',
                help="Only preview what the publisher would do.")
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
                if isinstance(cfg, dict):
                    pub_type = cfg.get('type')
                    if pub_type:
                        desc = cfg.get('description')
                        bake_first = cfg.get('bake', True)
                        msg = '%s (%s)' % (name, pub_type)
                        if not bake_first:
                            msg += ' (no local baking)'
                        if desc:
                            msg += ': ' + desc
                        logger.info(msg)
                    else:
                        logger.error(
                                "%s (unknown type '%s')" % (name, pub_type))
                elif isinstance(cfg, str):
                    comps = urllib.parse.urlparse(str(cfg))
                    pub_name = find_publisher_name(ctx.app, comps.scheme)
                    if pub_name:
                        logger.info("%s (%s)" % (name, pub_name))
                    else:
                        logger.error(
                                "%s (unknown scheme '%s')" %
                                (name, comps.scheme))
                else:
                    logger.error(
                            "%s (incorrect configuration)" % name)
            return

        pub = Publisher(ctx.app)
        pub.run(
                ctx.args.target,
                preview=ctx.args.preview,
                log_file=ctx.args.log_publisher)

