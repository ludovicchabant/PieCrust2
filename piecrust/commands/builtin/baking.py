import os.path
import logging
import hashlib
from piecrust.baking.baker import Baker
from piecrust.baking.records import BakeRecord
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class BakeCommand(ChefCommand):
    def __init__(self):
        super(BakeCommand, self).__init__()
        self.name = 'bake'
        self.description = "Bakes your website into static HTML files."

    def setupParser(self, parser, app):
        parser.add_argument('-o', '--output',
                help="The directory to put all the baked HTML files into "
                     "(defaults to `_counter`)")
        parser.add_argument('-f', '--force',
                help="Force re-baking the entire website.",
                action='store_true')
        parser.add_argument('--portable',
                help="Uses relative paths for all URLs.",
                action='store_true')
        parser.add_argument('--no-assets',
                help="Don't process assets (only pages).",
                action='store_true')

    def run(self, ctx):
        baker = Baker(
                ctx.app,
                out_dir=ctx.args.output,
                force=ctx.args.force,
                portable=ctx.args.portable,
                no_assets=ctx.args.no_assets)
        if ctx.args.portable:
            # Disable pretty URLs because there's likely not going to be
            # a web server to handle serving default documents.
            ctx.app.config.set('site/pretty_urls', False)

        baker.bake()


class ShowRecordCommand(ChefCommand):
    def __init__(self):
        super(ShowRecordCommand, self).__init__()
        self.name = 'showrecord'
        self.description = "Shows the bake record for a given output directory."

    def setupParser(self, parser, app):
        parser.add_argument('output',
                help="The output directory for which to show the bake record "
                     "(defaults to `_counter`)",
                nargs='?')

    def run(self, ctx):
        out_dir = ctx.args.output or os.path.join(ctx.app.root_dir, '_counter')
        record_cache = ctx.app.cache.getCache('bake_r')
        record_name = hashlib.md5(out_dir).hexdigest() + '.record'
        if not record_cache.has(record_name):
            raise Exception("No record has been created for this output path. "
                            "Did you bake there yet?")

        record = BakeRecord.load(record_cache.getCachePath(record_name))
        logging.info("Bake record for: %s" % record.out_dir)
        logging.info("Last baked: %s" % record.bake_time)
        logging.info("Entries:")
        for entry in record.entries:
            logging.info(" - ")
            logging.info("   path: %s" % entry.path)
            logging.info("   source: %s" % entry.source_name)
            logging.info("   config: %s" % entry.config)
            logging.info("   base URL: %s" % entry.uri)
            logging.info("   outputs: %s" % entry.out_paths)
