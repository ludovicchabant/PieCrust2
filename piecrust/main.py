import sys
import time
import os.path
import logging
import argparse
import colorama
from piecrust.app import PieCrust, PieCrustConfiguration, APP_VERSION
from piecrust.chefutil import format_timed
from piecrust.environment import StandardEnvironment
from piecrust.pathutil import SiteNotFoundError, find_app_root
from piecrust.plugins.base import PluginLoader


logger = logging.getLogger(__name__)


class ColoredFormatter(logging.Formatter):
    COLORS = {
            'DEBUG': colorama.Fore.BLACK + colorama.Style.BRIGHT,
            'INFO': '',
            'WARNING': colorama.Fore.YELLOW,
            'ERROR': colorama.Fore.RED,
            'CRITICAL': colorama.Back.RED + colorama.Fore.WHITE
            }

    def __init__(self, fmt=None, datefmt=None):
        super(ColoredFormatter, self).__init__(fmt, datefmt)

    def format(self, record):
        color = self.COLORS.get(record.levelname)
        res = super(ColoredFormatter, self).format(record)
        if color:
            res = color + res + colorama.Style.RESET_ALL
        return res


class NullPieCrust:
    def __init__(self):
        self.root_dir = None
        self.debug = False
        self.templates_dirs = []
        self.plugins_dirs = []
        self.theme_dir = None
        self.cache_dir = None
        self.config = PieCrustConfiguration()
        self.plugin_loader = PluginLoader(self)
        self.env = StandardEnvironment()
        self.env.initialize(self)


def main():
    start_time = time.clock()

    # We need to parse some arguments before we can build the actual argument
    # parser, because it can affect which plugins will be loaded. Also, log-
    # related arguments must be parsed first because we want to log everything
    # from the beginning.
    root = None
    cache = True
    debug = False
    quiet = False
    log_file = None
    config_variant = None
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith('--root='):
            root = os.path.expanduser(arg[len('--root='):])
        elif arg == '--root':
            root = sys.argv[i + 1]
            ++i
        elif arg.startswith('--config='):
            config_variant = arg[len('--config='):]
        elif arg == '--config':
            config_variant = sys.argv[i + 1]
            ++i
        elif arg == '--log':
            log_file = sys.argv[i + 1]
            ++i
        elif arg == '--no-cache':
            cache = False
        elif arg == '--debug':
            debug = True
        elif arg == '--quiet':
            quiet = True

        if arg[0] != '-':
            break

        i = i + 1

    # Setup the logger.
    if debug and quiet:
        raise Exception("You can't specify both --debug and --quiet.")

    colorama.init()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    log_handler = logging.StreamHandler(sys.stdout)
    if debug:
        root_logger.setLevel(logging.DEBUG)
        log_handler.setFormatter(ColoredFormatter("[%(name)s] %(message)s"))
    else:
        if quiet:
            root_logger.setLevel(logging.WARNING)
        log_handler.setFormatter(ColoredFormatter("%(message)s"))
    root_logger.addHandler(log_handler)
    if log_file:
        root_logger.addHandler(logging.FileHandler(log_file))

    # Setup the app.
    if root is None:
        root = find_app_root()

    if not root:
        app = NullPieCrust()
    else:
        app = PieCrust(root, cache=cache)

    # Handle a configuration variant.
    if config_variant is not None:
        if not root:
            raise SiteNotFoundError()
        app.config.applyVariant('variants/' + config_variant)

    # Setup the arg parser.
    parser = argparse.ArgumentParser(
            description="The PieCrust chef manages your website.")
    parser.add_argument('--version', action='version', version=('%(prog)s ' + APP_VERSION))
    parser.add_argument('--root', help="The root directory of the website.")
    parser.add_argument('--config', help="The configuration variant to use for this command.")
    parser.add_argument('--debug', help="Show debug information.", action='store_true')
    parser.add_argument('--no-cache', help="When applicable, disable caching.", action='store_true')
    parser.add_argument('--quiet', help="Print only important information.", action='store_true')
    parser.add_argument('--log', help="Send log messages to the specified file.")

    commands = sorted(app.plugin_loader.getCommands(),
            lambda a, b: cmp(a.name, b.name))
    subparsers = parser.add_subparsers()
    for c in commands:
        p = subparsers.add_parser(c.name, help=c.description)
        c.setupParser(p, app)
        p.set_defaults(func=c._runFromChef)

    # Parse the command line.
    result = parser.parse_args()
    logger.debug(format_timed(start_time, 'initialized PieCrust'))

    # Run the command!
    exit_code = result.func(app, result)
    return exit_code

