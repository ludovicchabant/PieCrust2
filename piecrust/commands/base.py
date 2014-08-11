import logging
import functools
from piecrust.pathutil import SiteNotFoundError


logger = logging.getLogger(__name__)


class CommandContext(object):
    def __init__(self, app, args):
        self.app = app
        self.args = args
        self.result = 0


class ChefCommand(object):
    def __init__(self):
        self.name = '__unknown__'
        self.description = '__unknown__'
        self.requires_website = True

    def setupParser(self, parser, app):
        raise NotImplementedError()

    def run(self, ctx):
        raise NotImplementedError()

    def _runFromChef(self, app, res):
        if app.root_dir is None and self.requires_website:
            raise SiteNotFoundError()
        ctx = CommandContext(app, res)
        self.run(ctx)
        return ctx.result


class ExtendableChefCommand(ChefCommand):
    def __init__(self):
        super(ExtendableChefCommand, self).__init__()
        self._extensions = None

    def setupParser(self, parser, app):
        self._loadExtensions(app)
        subparsers = parser.add_subparsers()
        for e in self._extensions:
            p = subparsers.add_parser(e.name, help=e.description)
            e.setupParser(p, app)
            p.set_defaults(func=e._runFromChef)

    def _loadExtensions(self, app):
        if self._extensions is not None:
            return
        self._extensions = []
        for e in app.plugin_loader.getCommandExtensions():
            if e.command_name == self.name and e.supports(app):
                self._extensions.append(e)


class ChefCommandExtension(ChefCommand):
    def __init__(self):
        super(ChefCommandExtension, self).__init__()
        self.command_name = '__unknown__'

    def supports(self, app):
        return True


class _WrappedCommand(ChefCommand):
    def __init__(self, func, name, description):
        super(_WrappedCommand, self).__init__()
        self.func = func
        self.name = name
        self.description = description

    def run(self, ctx):
        self.func(ctx)


def simple_command(f, name, description=None):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    cmd = _WrappedCommand(f, name, description)
    f.__command_class__ = cmd
    return wrapper


def get_func_command(f):
    return getattr(f, '__command_class__')

