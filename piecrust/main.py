import io
import sys
import time
import os.path
import logging
import argparse
import colorama
from piecrust import APP_VERSION
from piecrust.app import PieCrust, PieCrustConfiguration
from piecrust.chefutil import (
        format_timed, log_friendly_exception, print_help_item)
from piecrust.commands.base import CommandContext
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
        self.theme_dir = None
        self.cache_dir = None
        self.config = PieCrustConfiguration()
        self.plugin_loader = PluginLoader(self)
        self.env = None


def main():
    if sys.platform == 'darwin':
        # There's a bug on MacOSX that can cause Python to be confused
        # about the locale. Let's try to fix that.
        # See: http://bugs.python.org/issue18378
        import locale
        try:
            locale.getdefaultlocale()
        except ValueError:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

    argv = sys.argv
    pre_args = _pre_parse_chef_args(argv)
    try:
        exit_code = _run_chef(pre_args)
    except Exception as ex:
        if pre_args.debug:
            logger.exception(ex)
        else:
            log_friendly_exception(logger, ex)
        exit_code = 1
    sys.exit(exit_code)


class PreParsedChefArgs(object):
    def __init__(self, root=None, cache=True, debug=False, quiet=False,
                 log_file=None, log_debug=False, config_variant=None):
        self.root = root
        self.cache = cache
        self.debug = debug
        self.quiet = quiet
        self.log_file = log_file
        self.log_debug = log_debug
        self.config_variant = config_variant
        self.config_values = []


def _parse_config_value(arg):
    try:
        name, value = arg.split('=')
    except Exception:
        raise Exception("Invalid configuration name and value: %s" % arg)
    return (name, value)


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
            res.root = os.path.expanduser(argv[i + 1])
            i += 1
        elif arg.startswith('--config='):
            res.config_variant = arg[len('--config='):]
        elif arg == '--config':
            res.config_variant = argv[i + 1]
            i += 1
        elif arg.startswith('--config-set='):
            res.config_values.append(
                    _parse_config_value(arg[len('--config-set='):]))
        elif arg == '--config-set':
            res.config_values.append(_parse_config_value(argv[i + 1]))
            i += 1
        elif arg == '--log':
            res.log_file = argv[i + 1]
            i += 1
        elif arg == '--log-debug':
            res.log_debug = True
        elif arg == '--no-cache':
            res.cache = False
        elif arg == '--debug':
            res.debug = True
        elif arg == '--quiet':
            res.quiet = True
        else:
            break

        i = i + 1

    # Setup the logger.
    if res.debug and res.quiet:
        raise Exception("You can't specify both --debug and --quiet.")

    colorama.init()
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if res.debug or res.log_debug:
        root_logger.setLevel(logging.DEBUG)

    log_handler = logging.StreamHandler(sys.stdout)
    if res.debug:
        log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(ColoredFormatter("[%(name)s] %(message)s"))
    else:
        if res.quiet:
            log_handler.setLevel(logging.WARNING)
        else:
            log_handler.setLevel(logging.INFO)
        log_handler.setFormatter(ColoredFormatter("%(message)s"))
    root_logger.addHandler(log_handler)

    if res.log_file:
        file_handler = logging.FileHandler(res.log_file, mode='w')
        root_logger.addHandler(file_handler)
        if res.log_debug:
            file_handler.setLevel(logging.DEBUG)

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
        app = PieCrust(root, cache=pre_args.cache, debug=pre_args.debug)

    # Build a hash for a custom cache directory.
    cache_key = 'default'

    # Handle a configuration variant.
    if pre_args.config_variant is not None:
        if not root:
            raise SiteNotFoundError("Can't apply any variant.")
        app.config.applyVariant('variants/' + pre_args.config_variant)
        cache_key += ',variant=%s' % pre_args.config_variant
    for name, value in pre_args.config_values:
        logger.debug("Setting configuration '%s' to: %s" % (name, value))
        app.config.set(name, value)
        cache_key += ',%s=%s' % (name, value)

    # Setup the arg parser.
    parser = argparse.ArgumentParser(
            prog='chef',
            description="The PieCrust chef manages your website.",
            formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
            '--version',
            action='version',
            version=('%(prog)s ' + APP_VERSION))
    parser.add_argument(
            '--root',
            help="The root directory of the website.")
    parser.add_argument(
            '--config',
            help="The configuration variant to use for this command.")
    parser.add_argument(
            '--config-set',
            help="Sets a specific site configuration setting.")
    parser.add_argument(
            '--debug',
            help="Show debug information.", action='store_true')
    parser.add_argument(
            '--no-cache',
            help="When applicable, disable caching.",
            action='store_true')
    parser.add_argument(
            '--quiet',
            help="Print only important information.",
            action='store_true')
    parser.add_argument(
            '--log',
            help="Send log messages to the specified file.")
    parser.add_argument(
            '--log-debug',
            help="Log debug messages to the log file.",
            action='store_true')

    commands = sorted(app.plugin_loader.getCommands(),
                      key=lambda c: c.name)
    subparsers = parser.add_subparsers(title='list of commands')
    for c in commands:
        p = subparsers.add_parser(c.name, help=c.description)
        c.setupParser(p, app)
        p.set_defaults(func=c.checkedRun)
        p.set_defaults(cache_name=c.cache_name)

    help_cmd = next(filter(lambda c: c.name == 'help', commands), None)
    if help_cmd and help_cmd.has_topics:
        with io.StringIO() as epilog:
            epilog.write("additional help topics:\n")
            for name, desc in help_cmd.getTopics():
                print_help_item(epilog, name, desc)
            parser.epilog = epilog.getvalue()

    # Parse the command line.
    result = parser.parse_args()
    logger.debug(format_timed(start_time, 'initialized PieCrust',
                              colored=False))

    # Print the help if no command was specified.
    if not hasattr(result, 'func'):
        parser.print_help()
        return 0

    # Use a customized cache for the command and current config.
    if result.cache_name != 'default' or cache_key != 'default':
        app.useSubCache(result.cache_name, cache_key)

    # Run the command!
    ctx = CommandContext(app, parser, result)
    exit_code = result.func(ctx)
    if exit_code is None:
        return 0
    if not isinstance(exit_code, int):
        logger.error("Got non-integer exit code: %s" % exit_code)
        return -1
    return exit_code

