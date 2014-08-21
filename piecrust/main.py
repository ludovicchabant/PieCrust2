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
    argv = sys.argv
    pre_args = _pre_parse_chef_args(argv)
    try:
        return _run_chef(pre_args)
    except Exception as ex:
        if pre_args.debug:
            logger.exception(ex)
        else:
            logger.error(str(ex))


class PreParsedChefArgs(object):
    def __init__(self, root=None, cache=True, debug=False, quiet=False,
            log_file=None, config_variant=None):
        self.root = root
        self.cache = cache
        self.debug = debug
        self.quiet = quiet
        self.log_file = log_file
        self.config_variant = config_variant


def _pre_parse_chef_args(argv):
    # We need to parse some arguments before we can build the actual argument
    # parser, because it can affect which plugins will be loaded. Also, log-
    # related arguments must be parsed first because we want to log everything
    # from the beginning.
    res = PreParsedChefArgs()
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg.startswith('--root='):
            res.root = os.path.expanduser(arg[len('--root='):])
        elif arg == '--root':
            res.root = argv[i + 1]
            ++i
        elif arg.startswith('--config='):
            res.config_variant = arg[len('--config='):]
        elif arg == '--config':
            res.config_variant = argv[i + 1]
            ++i
        elif arg == '--log':
            res.log_file = argv[i + 1]
            ++i
        elif arg == '--no-cache':
            res.cache = False
        elif arg == '--debug':
            res.debug = True
        elif arg == '--quiet':
            res.quiet = True

        if arg[0] != '-':
            break

        i = i + 1

    # Setup the logger.
    if res.debug and res.quiet:
        raise Exception("You can't specify both --debug and --quiet.")

    colorama.init()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    log_handler = logging.StreamHandler(sys.stdout)
    if res.debug:
        root_logger.setLevel(logging.DEBUG)
        log_handler.setFormatter(ColoredFormatter("[%(name)s] %(message)s"))
    else:
        if res.quiet:
            root_logger.setLevel(logging.WARNING)
        log_handler.setFormatter(ColoredFormatter("%(message)s"))
    root_logger.addHandler(log_handler)
    if res.log_file:
        root_logger.addHandler(logging.FileHandler(res.log_file))

    return res


def _run_chef(pre_args):
    # Setup the app.
    start_time = time.clock()
    root = pre_args.root
    if root is None:
        try:
            root = find_app_root()
        except SiteNotFoundError:
            root = None

    if not root:
        app = NullPieCrust()
    else:
        app = PieCrust(root, cache=pre_args.cache)

    # Handle a configuration variant.
    if pre_args.config_variant is not None:
        if not root:
            raise SiteNotFoundError("Can't apply any variant.")
        app.config.applyVariant('variants/' + pre_args.config_variant)

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
            key=lambda c: c.name)
    subparsers = parser.add_subparsers()
    for c in commands:
        p = subparsers.add_parser(c.name, help=c.description)
        c.setupParser(p, app)
        p.set_defaults(func=c._runFromChef)

    # Parse the command line.
    result = parser.parse_args()
    logger.debug(format_timed(start_time, 'initialized PieCrust', colored=False))

    # Run the command!
    exit_code = result.func(app, result)
    return exit_code

