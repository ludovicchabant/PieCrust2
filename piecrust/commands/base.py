import os.path
import logging
import argparse
import textwrap
import functools
from piecrust import RESOURCES_DIR
from piecrust.pathutil import SiteNotFoundError


logger = logging.getLogger(__name__)


class CommandContext(object):
    def __init__(self, appfactory, app, parser, args):
        self.appfactory = appfactory
        self.app = app
        self.parser = parser
        self.args = args


class ChefCommand(object):
    def __init__(self):
        self.name = '__unknown__'
        self.description = '__unknown__'
        self.requires_website = True
        self.cache_name = 'default'

    def setupParser(self, parser, app):
        raise NotImplementedError()

    def provideExtensions(self):
        return None

    def run(self, ctx):
        raise NotImplementedError(
            "Command '%s' doesn't implement the `run` "
            "method." % type(self))

    def checkedRun(self, ctx):
        if ctx.app.root_dir is None and self.requires_website:
            raise SiteNotFoundError(theme=ctx.app.theme_site)
        return self.run(ctx)


class ExtendableChefCommand(ChefCommand):
    def __init__(self):
        super(ExtendableChefCommand, self).__init__()
        self._extensions = None

    def getExtensions(self, app):
        self._loadExtensions(app)
        return self._extensions

    def setupExtensionParsers(self, subparsers, app):
        for e in self.getExtensions(app):
            p = subparsers.add_parser(e.name, help=e.description)
            e.setupParser(p, app)
            p.set_defaults(sub_func=e.checkedRun)

    def _loadExtensions(self, app):
        if self._extensions is not None:
            return

        possible_exts = []
        for e in app.plugin_loader.getCommandExtensions():
            possible_exts.append(e)
        for c in app.plugin_loader.getCommands():
            exts = c.provideExtensions()
            if exts is not None:
                possible_exts += exts

        self._extensions = list(filter(
            lambda e: e.command_name == self.name and e.supports(app),
            possible_exts))


class ChefCommandExtension(object):
    command_name = '__unknown__'

    def supports(self, app):
        return True


class HelpCommand(ExtendableChefCommand):
    def __init__(self):
        super(HelpCommand, self).__init__()
        self.name = 'help'
        self.description = "Prints help about PieCrust's chef."
        self.requires_website = False
        self._topic_providers = []

    @property
    def has_topics(self):
        return len(self._topic_providers) > 0

    def getTopics(self):
        return [(n, d) for (n, d, e) in self._topic_providers]

    def setupParser(self, parser, app):
        parser.add_argument(
            'topic', nargs='?',
            help="The command name or topic on which to get help.")

        extensions = self.getExtensions(app)
        for ext in extensions:
            for name, desc in ext.getHelpTopics():
                self._topic_providers.append((name, desc, ext))

    def run(self, ctx):
        topic = ctx.args.topic

        if topic is None:
            ctx.parser.print_help()
            return 0

        for name, desc, ext in self._topic_providers:
            if name == topic:
                print(ext.getHelpTopic(topic, ctx.app))
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


def _get_help_topic_from_resources(command_name, topic):
    path = os.path.join(RESOURCES_DIR, 'helptopics',
                        '%s_%s.txt' % (command_name, topic))
    with open(path, 'r', encoding='utf8') as fp:
        lines = fp.readlines()

    wrapped_lines = []
    for ln in lines:
        ln = ln.rstrip('\n')
        if not ln:
            wrapped_lines.append('')
        else:
            wrapped_lines += textwrap.wrap(ln, width=80)
    return '\n'.join(wrapped_lines)


class _ResourcesHelpTopics:
    def getHelpTopic(self, topic, app):
        category = self.__class__.__name__.lower()
        if category.endswith('helptopic'):
            category = category[:-len('helptopic')]
        return _get_help_topic_from_resources(category, topic)
