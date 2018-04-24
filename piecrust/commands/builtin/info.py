import os
import os.path
import logging
from piecrust.commands.base import (
    ChefCommand, ChefCommandExtension, _ResourcesHelpTopics)


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
        self.description = ("Shows the website's configuration.")

    def setupParser(self, parser, app):
        parser.add_argument(
            'path',
            help="The path to a config section or value",
            nargs='?')

    def run(self, ctx):
        import yaml
        from piecrust.configuration import ConfigurationDumper

        if ctx.args.path:
            show = ctx.app.config.get(ctx.args.path)
        else:
            show = ctx.app.config.getAll()

        if show is not None:
            if isinstance(show, (dict, list)):
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
            logger.debug("    class: %s" % type(src))
            desc = src.describe()
            if isinstance(desc, dict):
                for k, v in desc.items():
                    logger.info("    %s: %s" % (k, v))


class ShowRoutesCommand(ChefCommand):
    def __init__(self):
        super(ShowRoutesCommand, self).__init__()
        self.name = 'routes'
        self.description = "Shows the routes defined for this website."

    def setupParser(self, parser, app):
        pass

    def provideExtensions(self):
        return [RoutesHelpTopic()]

    def run(self, ctx):
        for route in ctx.app.routes:
            logger.info("%s:" % route.uri_pattern)
            logger.info("    source: %s" % (route.source_name or ''))
            logger.info("    regex: %s" % route.uri_re.pattern)
            logger.info("    function: %s(%s)" % (
                route.func_name,
                ', '.join(route.uri_params)))


class RoutesHelpTopic(ChefCommandExtension, _ResourcesHelpTopics):
    command_name = 'help'

    def getHelpTopics(self):
        return [('routes_config',
                 "Specifying URL routes for your site's content."),
                ('routes_params',
                 "Show the available route parameters.")]

    def getHelpTopic(self, topic, app):
        if topic != 'routes_params':
            return _ResourcesHelpTopics.getHelpTopic(self, topic, app)

        import textwrap

        help_txt = (
            textwrap.fill(
                "Route parameters can be used as placeholders when specifying "
                "route URL patterns in your site configuration. See "
                "`chef help routes_config` for more information.") +
            "\n\n")
        if app.root_dir is None:
            help_txt += textwrap.fill(
                "Running this help command in a PieCrust website would show "
                "the route parameters available for your site's sources. "
                "However, no PieCrust website has been found in the current "
                "working directory. ")
            return help_txt

        srcs_by_types = {}
        for src in app.sources:
            srcs_by_types.setdefault(src.SOURCE_NAME, []).append(src)

        for type_name, srcs in srcs_by_types.items():
            help_txt += textwrap.fill(
                "Route parameters for '%s' sources (%s):" % (
                    type_name, ', '.join([s.name for s in srcs])))
            help_txt += "\n"
            for rp in srcs[0].getSupportedRouteParameters():
                help_txt += " - %s\n" % rp.param_name
            help_txt += "\n"
        return help_txt


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
        import fnmatch
        from piecrust.sources.fs import FSContentSourceBase

        pattern = ctx.args.pattern
        sources = list(ctx.app.sources)
        if not ctx.args.exact and pattern is not None:
            pattern = '*%s*' % pattern

        for src in sources:
            if not ctx.args.include_theme and src.is_theme_source:
                continue
            if ctx.args.name and not fnmatch.fnmatch(src.name, ctx.args.name):
                continue

            is_fs_src = isinstance(src, FSContentSourceBase)
            items = src.getAllContents()
            for item in items:
                if ctx.args.metadata:
                    logger.info("spec:%s" % item.spec)
                    for key, val in item.metadata.items():
                        logger.info("%s:%s" % (key, val))
                    logger.info("---")
                else:
                    if is_fs_src:
                        name = os.path.relpath(item.spec, ctx.app.root_dir)
                        if pattern is None or fnmatch.fnmatch(name, pattern):
                            if ctx.args.metadata:
                                logger.info("path:%s" % item.spec)
                                for key, val in item.metadata.items():
                                    logger.info("%s:%s" % (key, val))
                                logger.info("---")
                            else:
                                if ctx.args.full_path:
                                    name = item.spec
                                logger.info(name)
                    else:
                        if pattern is None or fnmatch.fnmatch(name, pattern):
                            logger.info(item.spec)


class UrlCommand(ChefCommand):
    def __init__(self):
        super().__init__()
        self.name = 'url'
        self.description = "Gets the URL to a given page."

    def setupParser(self, parser, app):
        parser.add_argument(
            'path',
            help="The path to the page.")
        parser.add_argument(
            '-f', '--func',
            dest='tpl_func',
            action='store_true',
            help="Return the template function call instead of the URL.")

    def run(self, ctx):
        from piecrust.sources.fs import FSContentSourceBase
        from piecrust.routing import RouteParameter

        # Find which source this page might belong to.
        full_path = os.path.join(ctx.app.root_dir, ctx.args.path)
        for src in ctx.app.sources:
            if not isinstance(src, FSContentSourceBase):
                continue

            if full_path.startswith(src.fs_endpoint_path + os.sep):
                parent_src = src
                break
        else:
            raise Exception("Can't find which source this page belongs to.")

        route = ctx.app.getSourceRoute(parent_src.name)
        content_item = parent_src.findContentFromSpec(full_path)
        route_params = content_item.metadata['route_params']

        if ctx.args.tpl_func:
            if not route.func_name:
                raise Exception("Source '%s' doesn't have a route with "
                                "a template function name defined." %
                                parent_src.name)

            url = '%s(' % route.func_name
            for i, p in enumerate(route.uri_params):
                if i > 0:
                    url += ', '
                pinfo = route.getParameter(p)
                if pinfo.param_type == RouteParameter.TYPE_INT2:
                    url += '%02d' % route_params[p]
                elif pinfo.param_type == RouteParameter.TYPE_INT4:
                    url += '%04d' % route_params[p]
                else:
                    url += str(route_params[p])
            url += ')'
            logger.info(url)
        else:
            url = route.getUri(route_params)
            logger.info(url)
