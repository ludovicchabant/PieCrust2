import logging
import argparse
import functools
from piecrust.pathutil import SiteNotFoundError


logger = logging.getLogger(__name__)


class CommandContext(object):
    def __init__(self, app, parser, args):
        self.app = app
        self.parser = parser
        self.args = args


class ChefCommand(object):
    def __init__(self):
        self.name = '__unknown__'
        self.description = '__unknown__'
        self.requires_website = True

    def setupParser(self, parser, app):
        raise NotImplementedError()

    def run(self, ctx):
        raise NotImplementedError("Command '%s' doesn't implement the `run` "
                "method." % type(self))

    def checkedRun(self, ctx):
        if ctx.app.root_dir is None and self.requires_website:
            raise SiteNotFoundError()
        return self.run(ctx)


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
            p.set_defaults(func=e.checkedRun)

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


class HelpCommand(ChefCommand):
    def __init__(self):
        super(HelpCommand, self).__init__()
        self.name = 'help'
        self.description = "Prints help about PieCrust's chef."
        self._topic_providers = {}

    @property
    def has_topics(self):
        return any(self._topic_providers)

    def addTopic(self, name, provider):
        self._topic_providers[name] = provider

    def getTopicNames(self):
        return self._topic_providers.keys()

    def setupParser(self, parser, app):
        parser.add_argument('topic', nargs='?',
                help="The command name or topic on which to get help.")

    def run(self, ctx):
        topic = ctx.args.topic

        if topic is None:
            ctx.parser.print_help()
            return 0

        if topic in self._topic_providers:
            print(self._topic_providers[topic].getHelpTopic(topic, ctx.app))
            return 0

        for c in ctx.app.plugin_loader.getCommands():
            if c.name == topic:
                fake = argparse.ArgumentParser(
                        prog='%s %s' % (ctx.parser.prog, c.name),
                        description=c.description)
                c.setupParser(fake, ctx.app)
                fake.print_help()
                return 0

        raise Exception("No such command or topic: %s" % topic)


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

