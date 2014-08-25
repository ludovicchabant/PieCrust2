import os
import os.path
import shutil
import codecs
import logging
import yaml
from piecrust.app import CONFIG_PATH
from piecrust.commands.base import ChefCommand
from piecrust.sources.base import IPreparingSource, MODE_CREATING


logger = logging.getLogger(__name__)


class InitCommand(ChefCommand):
    def __init__(self):
        super(InitCommand, self).__init__()
        self.name = 'init'
        self.description = "Creates a new empty PieCrust website."
        self.requires_website = False

    def setupParser(self, parser, app):
        parser.add_argument('destination',
                help="The destination directory in which to create the website.")

    def run(self, ctx):
        destination = ctx.args.destination
        if destination is None:
            destination = os.getcwd()

        if not os.path.isdir(destination):
            os.makedirs(destination, 0o755)

        config_path = os.path.join(destination, CONFIG_PATH)
        if not os.path.isdir(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path), 0o755)

        config_text = yaml.dump({
                'site': {
                    'title': "My New Website",
                    'description': "A website recently generated with PieCrust",
                    'pretty_urls': True
                    },
                'smartypants': {
                    'enable': True
                    }
                },
                default_flow_style=False)
        with codecs.open(config_path, 'w', 'utf-8') as fp:
            fp.write(config_text)


class PurgeCommand(ChefCommand):
    def __init__(self):
        super(PurgeCommand, self).__init__()
        self.name = 'purge'
        self.description = "Purges the website's cache."

    def setupParser(self, parser, app):
        pass

    def run(self, ctx):
        cache_dir = ctx.app.cache_dir
        if os.path.isdir(cache_dir):
            logger.info("Purging cache: %s" % cache_dir)
            shutil.rmtree(cache_dir)


class PrepareCommand(ChefCommand):
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
            p = subparsers.add_parser(src.item_name)
            src.setupPrepareParser(p, app)
            p.set_defaults(source=src)

    def run(self, ctx):
        app = ctx.app
        source = ctx.args.source
        metadata = source.buildMetadata(ctx.args)
        rel_path, metadata = source.findPagePath(metadata, MODE_CREATING)
        path = source.resolveRef(rel_path)
        name, ext = os.path.splitext(path)
        if ext == '.*':
            path = '%s.%s' % (name,
                    app.config.get('site/default_auto_format'))
        if os.path.exists(path):
            raise Exception("'%s' already exists." % path)

        logger.info("Creating page: %s" % os.path.relpath(path, app.root_dir))
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path), 0o755)
        with open(path, 'w') as f:
            f.write('---\n')
            f.write('title: %s\n' % 'Unknown title')
            f.write('---\n')
            f.write("This is a new page!\n")

