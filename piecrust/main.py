import os
import os.path
import io
import sys
import time
import hashlib
import logging
import argparse
import colorama
from piecrust import APP_VERSION
from piecrust.app import (
    PieCrustFactory, PieCrustConfiguration)
from piecrust.chefutil import (
    format_timed, log_friendly_exception, print_help_item)
from piecrust.commands.base import CommandContext
from piecrust.pathutil import SiteNotFoundError, find_app_root
from piecrust.plugins.base import PluginLoader


logger = logging.getLogger(__name__)

_chef_start_time = time.perf_counter()


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
    def __init__(self, theme_site=False):
        self.theme_site = theme_site
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

    argv = sys.argv[1:]
    pre_args = _pre_parse_chef_args(argv)
    try:
        exit_code = _run_chef(pre_args, argv)
    except Exception as ex:
        if pre_args.debug:
            logger.exception(ex)
        else:
            log_friendly_exception(logger, ex)
        exit_code = 1
    sys.exit(exit_code)


def _setup_main_parser_arguments(parser):
    parser.add_argument(
        '--version',
        action='version',
        version=('%(prog)s ' + APP_VERSION))
    parser.add_argument(
        '--root',
        help="The root directory of the website.")
    parser.add_argument(
        '--theme',
        action='store_true',
        help="Makes the current command apply to a theme website.")
    parser.add_argument(
        '--config',
        action='append',
        dest='config_variants',
        help="The configuration variant(s) to use for this command.")
    parser.add_argument(
        '--config-set',
        nargs=2,
        metavar=('NAME', 'VALUE'),
        action='append',
        dest='config_values',
        help="Sets a specific site configuration setting.")
    parser.add_argument(
        '--debug',
        help="Show debug information.", action='store_true')
    parser.add_argument(
        '--debug-only',
        action='append',
        help="Only show debug information for the given categories.")
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
        dest='log_file',
        help="Send log messages to the specified file.")
    parser.add_argument(
        '--log-debug',
        help="Log debug messages to the log file.",
        action='store_true')
    parser.add_argument(
        '--no-color',
        help="Don't use colorized output.",
        action='store_true')
    parser.add_argument(
        '--pid-file',
        dest='pid_file',
        help="Write a PID file for the current process.")


""" Kinda hacky, but we want the `serve` command to use a different cache
so that PieCrust doesn't need to re-render all the pages when going
between `serve` and `bake` (or, worse, *not* re-render them all correctly
and end up serving or baking the wrong version).
"""
_command_caches = {
    'serve': 'server'}


def _make_chef_state():
    return []


def _recover_pre_chef_state(state):
    for s in state:
        s()


def _pre_parse_chef_args(argv, *, bypass_setup=False, state=None):
    # We need to parse some arguments before we can build the actual argument
    # parser, because it can affect which plugins will be loaded. Also, log-
    # related arguments must be parsed first because we want to log everything
    # from the beginning.
    parser = argparse.ArgumentParser()
    _setup_main_parser_arguments(parser)
    parser.add_argument('extra_args', nargs=argparse.REMAINDER)
    res, _ = parser.parse_known_args(argv)
    if bypass_setup:
        return res

    # Setup the logger.
    if res.debug and res.quiet:
        raise Exception("You can't specify both --debug and --quiet.")

    strip_colors = None
    if res.no_color:
        strip_colors = True

    colorama.init(strip=strip_colors)
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    if res.debug or res.log_debug:
        root_logger.setLevel(logging.DEBUG)
    if state is not None:
        state.append(lambda: root_logger.setLevel(previous_level))

    if res.debug_only:
        for n in res.debug_only:
            sub_logger = logging.getLogger(n)
            previous_level = sub_logger.level
            sub_logger.setLevel(logging.DEBUG)
            if state is not None:
                state.append(lambda: sub_logger.setLevel(previous_level))

    log_handler = logging.StreamHandler(sys.stdout)
    if res.debug or res.debug_only:
        log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(ColoredFormatter("[%(name)s] %(message)s"))
    else:
        if res.quiet:
            log_handler.setLevel(logging.WARNING)
        else:
            log_handler.setLevel(logging.INFO)
        log_handler.setFormatter(ColoredFormatter("%(message)s"))
    root_logger.addHandler(log_handler)
    if state is not None:
        state.append(lambda: root_logger.removeHandler(log_handler))

    if res.log_file:
        file_handler = logging.FileHandler(res.log_file, mode='w')
        root_logger.addHandler(file_handler)
        if res.log_debug:
            file_handler.setLevel(logging.DEBUG)
        if state is not None:
            state.append(lambda: root_logger.removeHandler(file_handler))

    # PID file.
    if res.pid_file:
        try:
            pid_file_dir = os.path.dirname(res.pid_file)
            if pid_file_dir and not os.path.isdir(pid_file_dir):
                os.makedirs(pid_file_dir)

            with open(res.pid_file, 'w') as fp:
                fp.write(str(os.getpid()))
        except OSError as ex:
            raise Exception("Can't write PID file: %s" % res.pid_file) from ex

    return res


def _build_cache_key(pre_args):
    cache_key_str = 'default'
    if pre_args.extra_args:
        cmd_name = pre_args.extra_args[0]
        if cmd_name in _command_caches:
            cache_key_str = _command_caches[cmd_name]
    if pre_args.config_variants:
        for value in pre_args.config_variants:
            cache_key_str += ',variant=%s' % value
    if pre_args.config_values:
        for name, value in pre_args.config_values:
            cache_key_str += ',%s=%s' % (name, value)

    logger.debug("Using cache key: %s" % cache_key_str)
    cache_key = hashlib.md5(cache_key_str.encode('utf8')).hexdigest()
    return cache_key


def _setup_app_environment(app, env):
    from piecrust.uriutil import multi_replace

    tokens = {
        '%root_dir%': app.root_dir}

    for k, v in env.items():
        varname = k
        append = False
        if k.lower() == 'path':
            append = True
            v = os.pathsep + v
        elif k.endswith('+'):
            varname = k[:-1]
            append = True

        v = multi_replace(v, tokens)

        if append:
            logger.debug("Env: $%s += %s" % (varname, v))
            os.environ[varname] += v
        else:
            logger.debug("Env: $%s = %s" % (varname, v))
            os.environ[varname] = v


def _run_chef(pre_args, argv):
    # Setup the app.
    root = None
    if pre_args.root:
        root = os.path.expanduser(pre_args.root)
    else:
        try:
            root = find_app_root(theme=pre_args.theme)
        except SiteNotFoundError:
            root = None

    # Can't apply custom configuration stuff if there's no website.
    if (pre_args.config_variants or pre_args.config_values) and not root:
        raise SiteNotFoundError(
            "Can't apply any configuration variant or value overrides, "
            "there is no website here.")

    if root:
        cache_key = None
        if not pre_args.no_cache:
            cache_key = _build_cache_key(pre_args)
        appfactory = PieCrustFactory(
            root,
            theme_site=pre_args.theme,
            cache=(not pre_args.no_cache),
            cache_key=cache_key,
            debug=pre_args.debug,
            config_variants=pre_args.config_variants,
            config_values=pre_args.config_values)
        app = appfactory.create()
    else:
        appfactory = None
        app = NullPieCrust(
            theme_site=pre_args.theme)

    # Setup the arg parser.
    parser = argparse.ArgumentParser(
        prog='chef',
        description="The PieCrust chef manages your website.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    _setup_main_parser_arguments(parser)

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
    result = parser.parse_args(argv)
    logger.debug(format_timed(_chef_start_time, 'initialized PieCrust',
                              colored=False))

    # Print the help if no command was specified.
    if not hasattr(result, 'func'):
        parser.print_help()
        return 0

    # Do any custom setup the user wants.
    custom_env = app.config.get('chef/env')
    if custom_env:
        _setup_app_environment(app, custom_env)

    # Add some timing information.
    if app.env:
        app.env.stats.registerTimer('ChefStartup')
        app.env.stats.stepTimerSince('ChefStartup', _chef_start_time)

    # Run the command!
    ctx = CommandContext(appfactory, app, parser, result)
    exit_code = result.func(ctx)
    if exit_code is None:
        return 0
    if not isinstance(exit_code, int):
        logger.error("Got non-integer exit code: %s" % exit_code)
        return -1
    return exit_code

