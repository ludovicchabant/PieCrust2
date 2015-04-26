import os
import os.path
import re
import io
import time
import glob
import logging
import textwrap
from piecrust import RESOURCES_DIR
from piecrust.chefutil import print_help_item
from piecrust.commands.base import ExtendableChefCommand, ChefCommandExtension
from piecrust.sources.base import MODE_CREATING
from piecrust.sources.interfaces import IPreparingSource
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


def make_title(slug):
    slug = re.sub(r'[\-_]', ' ', slug)
    return slug.title()


class PrepareCommand(ExtendableChefCommand):
    """ Chef command for creating pages with some default content.
    """
    def __init__(self):
        super(PrepareCommand, self).__init__()
        self.name = 'prepare'
        self.description = "Prepares new content for your website."

    def setupParser(self, parser, app):
        # Don't setup anything if this is a null app
        # (for when `chef` is run from outside a website)
        if app.root_dir is None:
            return

        subparsers = parser.add_subparsers()
        for src in app.sources:
            if not isinstance(src, IPreparingSource):
                logger.debug("Skipping source '%s' because it's not "
                             "preparable." % src.name)
                continue
            if src.is_theme_source:
                logger.debug("Skipping source '%s' because it's a theme "
                             "source." % src.name)
                continue
            p = subparsers.add_parser(
                    src.item_name,
                    help=("Creates an empty page in the '%s' source." %
                          src.name))
            src.setupPrepareParser(p, app)
            p.add_argument('-t', '--template', default='default',
                           help="The template to use, which will change the "
                                "generated text and header.")
            p.set_defaults(source=src)

    def run(self, ctx):
        if not hasattr(ctx.args, 'source'):
            raise Exception("No source specified. "
                            "Please run `chef prepare -h` for usage.")

        app = ctx.app
        source = ctx.args.source
        metadata = source.buildMetadata(ctx.args)
        factory = source.findPageFactory(metadata, MODE_CREATING)
        path = factory.path
        name, ext = os.path.splitext(path)
        if ext == '.*':
            path = '%s.%s' % (
                    name,
                    app.config.get('site/default_auto_format'))
        if os.path.exists(path):
            raise Exception("'%s' already exists." % path)

        tpl_name = ctx.args.template
        extensions = self.getExtensions(app)
        ext = next(
                filter(
                    lambda e: tpl_name in e.getTemplateNames(ctx.app),
                    extensions),
                None)
        if ext is None:
            raise Exception("No such page template: %s" % tpl_name)

        tpl_text = ext.getTemplate(ctx.app, tpl_name)
        if tpl_text is None:
            raise Exception("Error loading template: %s" % tpl_name)
        title = (metadata.get('slug') or metadata.get('path') or
                 'Untitled page')
        title = make_title(title)
        tokens = {
                '%title%': title,
                '%time.today%': time.strftime('%Y/%m/%d'),
                '%time.now%': time.strftime('%H:%M:%S')}
        tpl_text = multi_replace(tpl_text, tokens)

        logger.info("Creating page: %s" % os.path.relpath(path, app.root_dir))
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path), 0o755)

        with open(path, 'w') as f:
            f.write(tpl_text)


class DefaultPrepareTemplatesCommandExtension(ChefCommandExtension):
    """ Provides the default scaffolding templates to the `prepare`
        command.
    """
    def __init__(self):
        super(DefaultPrepareTemplatesCommandExtension, self).__init__()
        self.command_name = 'prepare'

    def getTemplateNames(self, app):
        return ['default', 'rss', 'atom']

    def getTemplateDescription(self, app, name):
        descs = {
                'default': "The default template, for a simple page.",
                'rss': "A fully functional RSS feed.",
                'atom': "A fully functional Atom feed."}
        return descs[name]

    def getTemplate(self, app, name):
        assert name in ['default', 'rss', 'atom']
        src_path = os.path.join(RESOURCES_DIR, 'prepare', '%s.html' % name)
        with open(src_path, 'r', encoding='utf8') as fp:
            return fp.read()


class UserDefinedPrepareTemplatesCommandExtension(ChefCommandExtension):
    """ Provides user-defined scaffolding templates to the `prepare`
        command.
    """
    def __init__(self):
        super(UserDefinedPrepareTemplatesCommandExtension, self).__init__()
        self.command_name = 'prepare'

    def _getTemplatesDir(self, app):
        return os.path.join(app.root_dir, 'scaffold/pages')

    def supports(self, app):
        return os.path.isdir(self._getTemplatesDir(app))

    def getTemplateNames(self, app):
        names = os.listdir(self._getTemplatesDir(app))
        return map(lambda n: os.path.splitext(n)[0], names)

    def getTemplateDescription(self, app, name):
        return "User-defined template."

    def getTemplate(self, app, name):
        templates_dir = self._getTemplatesDir(app)
        pattern = os.path.join(templates_dir, '%s.*' % name)
        matches = glob.glob(pattern)
        if not matches:
            raise Exception("No such page scaffolding template: %s" % name)
        if len(matches) > 1:
            raise Exception(
                    "More than one scaffolding template has name: %s" % name)
        with open(matches[0], 'r', encoding='utf8') as fp:
            return fp.read()


class DefaultPrepareTemplatesHelpTopic(ChefCommandExtension):
    """ Provides help topics for the `prepare` command.
    """
    command_name = 'help'

    def getHelpTopics(self):
        return [('scaffolding',
                 "Available templates for the 'prepare' command.")]

    def getHelpTopic(self, topic, app):
        with io.StringIO() as tplh:
            extensions = app.plugin_loader.getCommandExtensions()
            for e in extensions:
                if e.command_name == 'prepare' and e.supports(app):
                    for n in e.getTemplateNames(app):
                        d = e.getTemplateDescription(app, n)
                        print_help_item(tplh, n, d)
            help_list = tplh.getvalue()

        help_txt = (
                textwrap.fill(
                    "Running the 'prepare' command will let "
                    "PieCrust setup a page for you in the correct place, with "
                    "some hopefully useful default text.") +
                "\n\n" +
                textwrap.fill("The following templates are available:") +
                "\n\n" +
                help_list)
        return help_txt

