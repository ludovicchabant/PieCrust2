import logging
from piecrust.commands.base import ChefCommand


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
            '--log-publisher',
            metavar='LOG_FILE',
            help="Log the publisher's output to a given file.")
        parser.add_argument(
            '--log-debug-info',
            action='store_true',
            help="Add some debug info as a preamble to the log file.")
        parser.add_argument(
            '--append-log',
            action='store_true',
            help="Append to the log file if it exists.")
        parser.add_argument(
            '--preview',
            action='store_true',
            help="Only preview what the publisher would do.")

        # Don't setup anything for a null app.
        if app.root_dir is None:
            return

        subparsers = parser.add_subparsers()
        for pub in app.publishers:
            p = subparsers.add_parser(
                pub.target,
                help="Publish using target '%s'." % pub.target)
            pub.setupPublishParser(p, app)
            p.set_defaults(sub_func=self._doPublish)
            p.set_defaults(target=pub.target)

        if not app.publishers:
            parser.epilog = (
                "No publishers have been defined. You can define publishers "
                "through the `publish` configuration settings. "
                "For more information see: "
                "https://bolt80.com/piecrust/en/latest/docs/publishing/")

    def checkedRun(self, ctx):
        from piecrust.pathutil import SiteNotFoundError

        if ctx.app.root_dir is None:
            raise SiteNotFoundError(theme=ctx.app.theme_site)

        if not hasattr(ctx.args, 'sub_func'):
            ctx.parser.parse_args(['publish', '--help'])
            return
        ctx.args.sub_func(ctx)

    def _doPublish(self, ctx):
        from piecrust.publishing.base import PublishingManager

        pub = PublishingManager(ctx.appfactory, ctx.app)
        pub.run(
            ctx.args.target,
            preview=ctx.args.preview,
            extra_args=ctx.args,
            log_file=ctx.args.log_publisher,
            log_debug_info=ctx.args.log_debug_info,
            append_log_file=ctx.args.append_log)

