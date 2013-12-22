import sys
import os.path
import logging
import argparse
from piecrust.app import PieCrust, PieCrustConfiguration, APP_VERSION
from piecrust.environment import StandardEnvironment
from piecrust.pathutil import SiteNotFoundError, find_app_root
from piecrust.plugins.base import PluginLoader


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
        format="%(message)s")


class NullPieCrust:
    def __init__(self):
        self.root = None
        self.cache = False
        self.debug = False
        self.templates_dirs = []
        self.pages_dir = []
        self.posts_dir = []
        self.plugins_dirs = []
        self.theme_dir = None
        self.cache_dir = None
        self.config = PieCrustConfiguration()
        self.plugin_loader = PluginLoader(self)
        self.env = StandardEnvironment()
        self.env.initialize(self)


def main():
    root = None
    cache = True
    debug = False
    config_variant = None
    i = 0
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
        elif arg == '--no-cache':
            cache = False
        elif arg == '--debug':
            debug = True

        if arg[0] != '-':
            break

    if debug:
        logger.setLevel(logging.DEBUG)

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
        c.setupParser(p)
        p.set_defaults(func=c._runFromChef)

    # Parse the command line.
    result = parser.parse_args()

    # Setup the logger.
    if result.debug and result.quiet:
        raise Exception("You can't specify both --debug and --quiet.")
    if result.debug:
        logger.setLevel(logging.DEBUG)
    elif result.quiet:
        logger.setLevel(logging.WARNING)
    if result.log:
        from logging.handlers import FileHandler
        logger.addHandler(FileHandler(result.log))

    # Run the command!
    result.func(app, result)


if __name__ == '__main__':
    main()

