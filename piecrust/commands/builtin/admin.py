import os
import logging
from piecrust.commands.base import ChefCommand


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
        p.set_defaults(sub_func=self._runFoodTruck)

    def checkedRun(self, ctx):
        if not hasattr(ctx.args, 'sub_func'):
            return self._runFoodTruck(ctx)
        return ctx.args.sub_func(ctx)

    def _runFoodTruck(self, ctx):
        from foodtruck import settings
        settings.FOODTRUCK_CMDLINE_MODE = True
        settings.FOODTRUCK_ROOT = ctx.app.root_dir
        from foodtruck.main import run_foodtruck
        run_foodtruck(debug=ctx.args.debug)

    def _initFoodTruck(self, ctx):
        import getpass
        import bcrypt

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
        import bcrypt
        binpw = ctx.args.password.encode('utf8')
        hashpw = bcrypt.hashpw(binpw, bcrypt.gensalt()).decode('utf8')
        logger.info(hashpw)

