import os
import os.path
import logging
from piecrust import CONFIG_PATH
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

    def checkedRun(self, ctx):
        if ctx.app.root_dir is None:
            raise SiteNotFoundError(theme=ctx.app.theme_site)

        if not hasattr(ctx.args, 'sub_func'):
            ctx.parser.parse_args(['admin', '--help'])
            return
        return ctx.args.sub_func(ctx)

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

