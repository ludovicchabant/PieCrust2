import logging
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class PluginsCommand(ChefCommand):
    def __init__(self):
        super(PluginsCommand, self).__init__()
        self.name = 'plugins'
        self.description = "Manage the plugins for the current website."

    def setupParser(self, parser, app):
        subparsers = parser.add_subparsers()
        p = subparsers.add_parser(
            'list',
            help="Lists the plugins installed in the current website.")
        p.add_argument(
            '-a', '--all',
            action='store_true',
            help=("Also list all the available plugins for the "
                  "current environment. The installed one will have an "
                  "asterix (*)."))
        p.set_defaults(sub_func=self._listPlugins)

    def checkedRun(self, ctx):
        from piecrust.pathutil import SiteNotFoundError

        if ctx.app.root_dir is None:
            raise SiteNotFoundError(theme=ctx.app.theme_site)

        if not hasattr(ctx.args, 'sub_func'):
            ctx.parser.parse_args(['plugins', '--help'])
            return
        ctx.args.sub_func(ctx)

    def _listPlugins(self, ctx):
        import pip

        names = {}
        installed_suffix = ''
        if ctx.args.all:
            prefix = 'PieCrust-'
            installed_packages = pip.get_installed_distributions()
            for plugin in installed_packages:
                if not plugin.project_name.startswith(prefix):
                    continue
                name = plugin.project_name[len(prefix):]
                names[name] = False
            installed_suffix = '*'

        for plugin in ctx.app.plugin_loader.plugins:
            names[plugin.name] = True

        for name, inst in names.items():
            logger.info("%s%s" % (name, installed_suffix if inst else ''))

