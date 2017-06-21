import os
import os.path
import logging
from piecrust import CACHE_DIR, CONFIG_PATH
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
        p.set_defaults(sub_func=self._initAdminSite)

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
        p.add_argument(
            '--use-reloader',
            help="Restart the server when PieCrust code changes",
            action='store_true')
        p.add_argument(
            '--use-debugger',
            help="Show the debugger when an error occurs",
            action='store_true')
        p.set_defaults(sub_func=self._runAdminSite)

    def checkedRun(self, ctx):
        if ctx.app.root_dir is None:
            raise SiteNotFoundError(theme=ctx.app.theme_site)

        if not hasattr(ctx.args, 'sub_func'):
            ctx.parser.parse_args(['admin', '--help'])
            return
        return ctx.args.sub_func(ctx)

    def _runAdminSite(self, ctx):
        # See `_run_sse_check` in `piecrust.serving.wrappers` for an
        # explanation of this check.
        if (ctx.args.monitor_assets and (
                not (ctx.args.debug or ctx.args.use_reloader) or
                os.environ.get('WERKZEUG_RUN_MAIN') == 'true')):
            from piecrust.serving.procloop import ProcessingLoop
            out_dir = os.path.join(
                ctx.app.root_dir, CACHE_DIR, 'admin', 'server')
            proc_loop = ProcessingLoop(ctx.appfactory, out_dir)
            proc_loop.start()

        es = {
            'FOODTRUCK_CMDLINE_MODE': True,
            'FOODTRUCK_ROOT': ctx.app.root_dir,
            'FOODTRUCK_URL_PREFIX': '',
            'SECRET_KEY': os.urandom(22),
            'LOGIN_DISABLED': True}
        if ctx.args.debug or ctx.args.use_debugger:
            es['DEBUG'] = True

        run_foodtruck(
            host=ctx.args.address,
            port=ctx.args.port,
            use_reloader=ctx.args.use_reloader,
            extra_settings=es)

    def _initAdminSite(self, ctx):
        import io
        import getpass
        from piecrust.admin import bcryptfallback as bcrypt

        secret_key = os.urandom(22)
        admin_username = input("Admin username (admin): ") or 'admin'
        admin_password = getpass.getpass("Admin password: ")
        if not admin_password:
            logger.warning("No administration password set!")
            logger.warning("Don't make this instance of the PieCrust "
                           "administration panel public.")
            logger.info("You can later set an admin password by editing "
                        "the `admin.cfg` file and using the "
                        "`chef admin genpass` command.")
        else:
            binpw = admin_password.encode('utf8')
            hashpw = bcrypt.hashpw(binpw, bcrypt.gensalt()).decode('utf8')
            admin_password = hashpw

        ft_config = """
admin:
    secret_key: %(secret_key)s
    username: %(username)s
    # You can generate another hashed password with `chef admin genpass`.
    password: %(password)s
"""
        ft_config = ft_config % {
            'secret_key': secret_key,
            'username': admin_username,
            'password': admin_password
        }

        config_path = os.path.join(ctx.app.root_dir, CONFIG_PATH)
        with open(config_path, 'a+', encoding='utf8') as fp:
            fp.seek(0, io.SEEK_END)
            fp.write('\n')
            fp.write(ft_config)

    def _generatePassword(self, ctx):
        from piecrust.admin import bcryptfallback as bcrypt
        binpw = ctx.args.password.encode('utf8')
        hashpw = bcrypt.hashpw(binpw, bcrypt.gensalt()).decode('utf8')
        logger.info(hashpw)


def run_foodtruck(host=None, port=None, use_reloader=False,
                  extra_settings=None):
    es = {}
    if extra_settings:
        es.update(extra_settings)

    # Disable PIN protection with Werkzeug's debugger.
    os.environ['WERKZEUG_DEBUG_PIN'] = 'off'

    try:
        from piecrust.admin.web import create_foodtruck_app
        app = create_foodtruck_app(es)
        app.run(host=host, port=port, use_reloader=use_reloader,
                threaded=True)
    except SystemExit:
        # This is needed for Werkzeug's code reloader to be able to correctly
        # shutdown the child process in order to restart it (otherwise, SSE
        # generators will keep it alive).
        try:
            from . import pubutil
            logger.debug("Shutting down SSE generators from main...")
            pubutil.server_shutdown = True
        except ImportError:
            pass
        raise

