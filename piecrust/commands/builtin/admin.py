import os
import os.path
import logging
from piecrust import CACHE_DIR
from piecrust.commands.base import ChefCommand
from piecrust.pathutil import SiteNotFoundError


logger = logging.getLogger(__name__)


class AdministrationPanelCommand(ChefCommand):
    def __init__(self):
        super(AdministrationPanelCommand, self).__init__()
        self.name = 'admin'
        self.description = "Manages the PieCrust administration panel."
        self.requires_website = False

    def setupParser(self, parser, app):
        subparsers = parser.add_subparsers()

        p = subparsers.add_parser(
                'init',
                help="Creates a new administration panel website.")
        p.set_defaults(sub_func=self._initFoodTruck)

        p = subparsers.add_parser(
                'genpass',
                help=("Generates the hashed password for use as an "
                      "admin password"))
        p.add_argument('password', help="The password to hash.")
        p.set_defaults(sub_func=self._generatePassword)

        p = subparsers.add_parser(
                'run',
                help="Runs the administrative panel website.")
        p.add_argument(
                '-p', '--port',
                help="The port for the administrative panel website.",
                default=8090)
        p.add_argument(
                '-a', '--address',
                help="The host for the administrative panel website.",
                default='localhost')
        p.add_argument(
                '--no-assets',
                help="Don't process and monitor the asset folder(s).",
                dest='monitor_assets',
                action='store_false')
        p.set_defaults(sub_func=self._runFoodTruck)

    def checkedRun(self, ctx):
        if ctx.app.root_dir is None:
            raise SiteNotFoundError(theme=ctx.app.theme_site)

        if not hasattr(ctx.args, 'sub_func'):
            ctx.parser.parse_args(['admin', '--help'])
            return
        return ctx.args.sub_func(ctx)

    def _runFoodTruck(self, ctx):
        # See `_run_sse_check` in `piecrust.serving.wrappers` for an explanation
        # of this check.
        if (ctx.args.monitor_assets and (
                not ctx.args.debug or
                os.environ.get('WERKZEUG_RUN_MAIN') == 'true')):
            from piecrust.app import PieCrustFactory
            from piecrust.serving.procloop import ProcessingLoop
            appfactory = PieCrustFactory(
                    ctx.app.root_dir,
                    cache=ctx.app.cache.enabled,
                    cache_key=ctx.app.cache_key,
                    config_variant=ctx.config_variant,
                    config_values=ctx.config_values,
                    debug=ctx.app.debug,
                    theme_site=ctx.app.theme_site)
            out_dir = os.path.join(ctx.app.root_dir, CACHE_DIR, 'foodtruck', 'server')
            proc_loop = ProcessingLoop(appfactory, out_dir)
            proc_loop.start()

        es = {
                'FOODTRUCK_CMDLINE_MODE': True,
                'FOODTRUCK_ROOT': ctx.app.root_dir}
        from piecrust.admin.main import run_foodtruck
        run_foodtruck(
                host=ctx.args.address,
                port=ctx.args.port,
                debug=ctx.args.debug,
                extra_settings=es)

    def _initFoodTruck(self, ctx):
        import getpass
        from piecrust.admin import bcryptfallback as bcrypt

        secret_key = os.urandom(22)
        admin_username = input("Admin username (admin): ") or 'admin'
        admin_password = getpass.getpass("Admin password: ")
        if not admin_password:
            logger.warning("No administration password set!")
            logger.warning("Don't make this instance of FoodTruck public.")
            logger.info("You can later set an admin password by editing "
                        "the `foodtruck.yml` file and using the "
                        "`chef admin genpass` command.")
        else:
            binpw = admin_password.encode('utf8')
            hashpw = bcrypt.hashpw(binpw, bcrypt.gensalt()).decode('utf8')
            admin_password = hashpw

        ft_config = """
security:
    username: %(username)s
    # You can generate another hashed password with `chef admin genpass`.
    password: %(password)s
"""
        ft_config = ft_config % {
                'username': admin_username,
                'password': admin_password
                }
        with open('foodtruck.yml', 'w', encoding='utf8') as fp:
            fp.write(ft_config)

        flask_config = """
SECRET_KEY = %(secret_key)s
"""
        flask_config = flask_config % {'secret_key': secret_key}
        with open('app.cfg', 'w', encoding='utf8') as fp:
            fp.write(flask_config)

    def _generatePassword(self, ctx):
        from piecrust.admin import bcryptfallback as bcrypt
        binpw = ctx.args.password.encode('utf8')
        hashpw = bcrypt.hashpw(binpw, bcrypt.gensalt()).decode('utf8')
        logger.info(hashpw)

