import os.path
import logging
import fnmatch
from piecrust.commands.base import ChefCommand
from piecrust.configuration import ConfigurationDumper


logger = logging.getLogger(__name__)


class RootCommand(ChefCommand):
    def __init__(self):
        super(RootCommand, self).__init__()
        self.name = 'root'
        self.description = "Gets the root directory of the current website."

    def setupParser(self, parser, app):
        pass

    def run(self, ctx):
        logger.info(ctx.app.root_dir)


class ShowConfigCommand(ChefCommand):
    def __init__(self):
        super(ShowConfigCommand, self).__init__()
        self.name = 'showconfig'
        self.description = ("Prints part of, or the entirety of, "
                            "the website's configuration.")

    def setupParser(self, parser, app):
        parser.add_argument(
                'path',
                help="The path to a config section or value",
                nargs='?')

    def run(self, ctx):
        show = ctx.app.config.get(ctx.args.path)
        if show is not None:
            if isinstance(show, (dict, list)):
                import yaml
                out = yaml.dump(show, default_flow_style=False,
                                Dumper=ConfigurationDumper)
                logger.info(out)
            else:
                logger.info(show)
        elif ctx.args.path:
            logger.error("No such configuration path: %s" % ctx.args.path)
            ctx.result = 1


class ShowSourcesCommand(ChefCommand):
    def __init__(self):
        super(ShowSourcesCommand, self).__init__()
        self.name = 'sources'
        self.description = "Shows the sources defined for this website."

    def setupParser(self, parser, app):
        pass

    def run(self, ctx):
        for src in ctx.app.sources:
            logger.info("%s:" % src.name)
            logger.info("    type: %s" % src.config.get('type'))
            logger.info("    class: %s" % type(src))


class ShowRoutesCommand(ChefCommand):
    def __init__(self):
        super(ShowRoutesCommand, self).__init__()
        self.name = 'routes'
        self.description = "Shows the routes defined for this website."

    def setupParser(self, parser, app):
        pass

    def run(self, ctx):
        for route in ctx.app.routes:
            logger.info("%s:" % route.uri_pattern)
            logger.info("    source: %s" % route.source_name)
            logger.info("    taxonomy: %s" % (route.taxonomy_name or ''))
            logger.info("    regex: %s" % route.uri_re.pattern)


class ShowPathsCommand(ChefCommand):
    def __init__(self):
        super(ShowPathsCommand, self).__init__()
        self.name = 'paths'
        self.description = "Shows the paths that this website is using."

    def setupParser(self, parser, app):
        pass

    def run(self, ctx):
        app = ctx.app
        paths = ['theme_dir', 'templates_dirs', 'cache_dir']
        for p in paths:
            value = getattr(app, p)
            if isinstance(value, list):
                logging.info("%s:" % p)
                for v in value:
                    logging.info("  - %s" % v)
            else:
                logging.info("%s: %s" % (p, value))


class FindCommand(ChefCommand):
    def __init__(self):
        super(FindCommand, self).__init__()
        self.name = 'find'
        self.description = "Find pages in the website."

    def setupParser(self, parser, app):
        parser.add_argument(
                'pattern',
                help="The pattern to match with page filenames",
                nargs='?')
        parser.add_argument(
                '-n', '--name',
                help="Limit the search to sources matching this name")
        parser.add_argument(
                '--full-path',
                help="Return full paths instead of root-relative paths",
                action='store_true')
        parser.add_argument(
                '--metadata',
                help="Return metadata about the page instead of just the path",
                action='store_true')
        parser.add_argument(
                '--include-theme',
                help="Include theme pages to the search",
                action='store_true')
        parser.add_argument(
                '--exact',
                help=("Match the exact given pattern, instead of any page "
                      "containing the pattern"),
                action='store_true')

    def run(self, ctx):
        pattern = ctx.args.pattern
        sources = list(ctx.app.sources)
        if not ctx.args.exact and pattern is not None:
            pattern = '*%s*' % pattern

        for src in sources:
            if not ctx.args.include_theme and src.is_theme_source:
                continue
            if ctx.args.name and not fnmatch.fnmatch(src.name, ctx.args.name):
                continue

            page_facs = src.getPageFactories()
            for pf in page_facs:
                name = os.path.relpath(pf.path, ctx.app.root_dir)
                if pattern is None or fnmatch.fnmatch(name, pattern):
                    if ctx.args.full_path:
                        name = pf.path
                    if ctx.args.metadata:
                        logger.info("path:%s" % pf.path)
                        for key, val in pf.metadata.items():
                            logger.info("%s:%s" % (key, val))
                        logger.info("---")
                    else:
                        logger.info(name)

