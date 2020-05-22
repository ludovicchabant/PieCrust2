import os
import os.path
import logging
from piecrust.commands.base import (
    ChefCommand, ExtendableChefCommand, ChefCommandExtension)


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
        from piecrust.sources.fs import FSContentSourceBase

        if not hasattr(ctx.args, 'source'):
            raise Exception("No source specified. "
                            "Please run `chef prepare -h` for usage.")
        source = ctx.args.source

        content_item = build_content(
            source,
            vars(ctx.args),
            ctx.args.template,
            force_overwrite=ctx.args.force)

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
        return ['default', 'micro', 'rss', 'atom']

    def getTemplateDescription(self, app, name):
        descs = {
            'default': "The default template, for a simple page.",
            'micro': "A micro-post.",
            'rss': "A fully functional RSS feed.",
            'atom': "A fully functional Atom feed."}
        return descs[name]

    def getTemplate(self, app, name):
        from piecrust import RESOURCES_DIR

        assert name in ['default', 'micro', 'rss', 'atom']
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


class CopyAssetCommand(ChefCommand):
    """ Chef command for copying files into a page's assets folder.
    """
    def __init__(self):
        super().__init__()
        self.name = 'copyasset'
        self.description = "Copies files into a page's assets folder."

    def setupParser(self, parser, app):
        parser.add_argument('path',
                            help="The path to the asset file.")
        parser.add_argument('page',
                            help="The path to the page file.")
        parser.add_argument('-n', '--rename',
                            help=("Rename the file so that it will be known "
                                  "by this name in the `{{assets}}` syntax."))

    def checkedRun(self, ctx):
        # TODO: suppor other types of sources...
        import shutil
        from piecrust.sources import mixins

        item = None
        spec = ctx.args.page
        for src in ctx.app.sources:
            if not isinstance(src, mixins.SimpleAssetsSubDirMixin):
                logger.warning(
                    "Ignoring source '%s' because it's not supported yet." %
                    src.name)
                continue

            try:
                item = src.findContentFromSpec(spec)
                break
            except Exception as ex:
                logger.warning(
                    "Ignoring source '%s' because it raised an error: %s" %
                    src.name, ex)
                continue

        if item is None:
            raise Exception("No such page: %s" % ctx.args.page)

        spec_no_ext, _ = os.path.splitext(item.spec)
        assets_dir = spec_no_ext + mixins.assets_suffix
        if not os.path.isdir(assets_dir):
            logger.info("Creating directory: %s" % assets_dir)
            os.makedirs(assets_dir)

        dest_name, dest_ext = os.path.splitext(os.path.basename(ctx.args.path))
        dest_name = ctx.args.rename or dest_name

        dest_path = os.path.join(assets_dir, dest_name + dest_ext)
        logger.info("Copying '%s' to '%s'." % (ctx.args.path, dest_path))
        shutil.copy2(ctx.args.path, dest_path)
