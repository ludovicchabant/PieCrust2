import os
import os.path
import logging
from piecrust.commands.base import ExtendableChefCommand, ChefCommandExtension


logger = logging.getLogger(__name__)


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

        from piecrust.sources.interfaces import IPreparingSource

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
                src.config['item_name'],
                help=("Creates an empty page in the '%s' source." %
                      src.name))
            src.setupPrepareParser(p, app)
            p.add_argument('-t', '--template', default='default',
                           help="The template to use, which will change the "
                           "generated text and header. Run `chef help "
                           "scaffolding` for more information.")
            p.add_argument('-f', '--force', action='store_true',
                           help="Overwrite any existing content.")
            p.set_defaults(source=src)
            p.set_defaults(sub_func=self._doRun)

    def checkedRun(self, ctx):
        from piecrust.pathutil import SiteNotFoundError

        if ctx.app.root_dir is None:
            raise SiteNotFoundError(theme=ctx.app.theme_site)

        if not hasattr(ctx.args, 'sub_func'):
            ctx.parser.parse_args(['prepare', '--help'])
            return
        ctx.args.sub_func(ctx)

    def _doRun(self, ctx):
        import time
        from piecrust.uriutil import multi_replace
        from piecrust.sources.fs import FSContentSourceBase

        if not hasattr(ctx.args, 'source'):
            raise Exception("No source specified. "
                            "Please run `chef prepare -h` for usage.")

        app = ctx.app
        tpl_name = ctx.args.template
        extensions = self.getExtensions(app)
        ext = next(
            filter(
                lambda e: tpl_name in e.getTemplateNames(app),
                extensions),
            None)
        if ext is None:
            raise Exception("No such page template: %s" % tpl_name)
        tpl_text = ext.getTemplate(app, tpl_name)
        if tpl_text is None:
            raise Exception("Error loading template: %s" % tpl_name)

        source = ctx.args.source
        content_item = source.createContent(vars(ctx.args))
        if content_item is None:
            raise Exception("Can't create item.")

        config_tokens = {
            '%title%': "Untitled Content",
            '%time.today%': time.strftime('%Y/%m/%d'),
            '%time.now%': time.strftime('%H:%M:%S')
        }
        config = content_item.metadata.get('config')
        if config:
            for k, v in config.items():
                config_tokens['%%%s%%' % k] = v
        tpl_text = multi_replace(tpl_text, config_tokens)

        logger.info("Creating content: %s" % content_item.spec)
        mode = 'w' if ctx.args.force else 'x'
        with source.openItem(content_item, mode) as f:
            f.write(tpl_text)

        # If this was a file-system content item, see if we need to auto-open
        # an editor on it.
        editor = ctx.app.config.get('prepare/editor')
        editor_type = ctx.app.config.get('prepare/editor_type', 'exe')
        if editor and isinstance(source, FSContentSourceBase):
            import shlex
            shell = False
            args = '%s "%s"' % (editor, content_item.spec)
            if '%path%' in editor:
                args = editor.replace('%path%', content_item.spec)

            if editor_type.lower() == 'shell':
                shell = True
            else:
                args = shlex.split(args)

            import subprocess
            logger.info("Running: %s" % args)
            subprocess.Popen(args, shell=shell)


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
        from piecrust import RESOURCES_DIR

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
        if not app.root_dir:
            return False
        return os.path.isdir(self._getTemplatesDir(app))

    def getTemplateNames(self, app):
        names = os.listdir(self._getTemplatesDir(app))
        return map(lambda n: os.path.splitext(n)[0], names)

    def getTemplateDescription(self, app, name):
        return "User-defined template."

    def getTemplate(self, app, name):
        import glob

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
        import io
        import textwrap
        from piecrust.chefutil import print_help_item

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
            help_list +
            "\n" +
            "You can add user-defined templates by creating pages in a "
            "`scaffold/pages` sub-directory in your website.")
        return help_txt

