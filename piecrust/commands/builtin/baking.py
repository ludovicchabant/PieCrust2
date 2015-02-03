import time
import os.path
import logging
import hashlib
import fnmatch
import datetime
from piecrust.baking.baker import Baker
from piecrust.baking.records import BakeRecord
from piecrust.chefutil import format_timed
from piecrust.commands.base import ChefCommand
from piecrust.processing.base import ProcessorPipeline
from piecrust.processing.records import (
        ProcessorPipelineRecord,
        FLAG_PREPARED, FLAG_PROCESSED, FLAG_OVERRIDEN,
        FLAG_BYPASSED_STRUCTURED_PROCESSING)


logger = logging.getLogger(__name__)


class BakeCommand(ChefCommand):
    def __init__(self):
        super(BakeCommand, self).__init__()
        self.name = 'bake'
        self.description = "Bakes your website into static HTML files."

    def setupParser(self, parser, app):
        parser.add_argument(
                '-o', '--output',
                help="The directory to put all the baked HTML files into "
                     "(defaults to `_counter`)")
        parser.add_argument(
                '-f', '--force',
                help="Force re-baking the entire website.",
                action='store_true')
        parser.add_argument(
                '--assets-only',
                help="Only bake the assets (don't bake the web pages).",
                action='store_true')
        parser.add_argument(
                '--html-only',
                help="Only bake HTML files (don't run the asset pipeline).",
                action='store_true')

    def run(self, ctx):
        out_dir = (ctx.args.output or
                   os.path.join(ctx.app.root_dir, '_counter'))

        success = True
        start_time = time.clock()
        try:
            # Bake the site sources.
            if not ctx.args.assets_only:
                success = success & self._bakeSources(ctx, out_dir)

            # Bake the assets.
            if not ctx.args.html_only:
                success = success & self._bakeAssets(ctx, out_dir)

            # All done.
            logger.info('-------------------------')
            logger.info(format_timed(start_time, 'done baking'))
            return 0 if success else 1
        except Exception as ex:
            if ctx.app.debug:
                logger.exception(ex)
            else:
                logger.error(str(ex))
            return 1

    def _bakeSources(self, ctx, out_dir):
        baker = Baker(
                ctx.app, out_dir,
                force=ctx.args.force)
        record = baker.bake()
        return record.success

    def _bakeAssets(self, ctx, out_dir):
        proc = ProcessorPipeline(
                ctx.app, out_dir,
                force=ctx.args.force)
        record = proc.run()
        return record.success


class ShowRecordCommand(ChefCommand):
    def __init__(self):
        super(ShowRecordCommand, self).__init__()
        self.name = 'showrecord'
        self.description = ("Shows the bake record for a given output "
                            "directory.")

    def setupParser(self, parser, app):
        parser.add_argument(
                '-o', '--output',
                help="The output directory for which to show the bake record "
                     "(defaults to `_counter`)",
                nargs='?')
        parser.add_argument(
                '-p', '--path',
                help="A pattern that will be used to filter the relative path "
                     "of entries to show.")

    def run(self, ctx):
        out_dir = ctx.args.output or os.path.join(ctx.app.root_dir, '_counter')
        record_name = (hashlib.md5(out_dir.encode('utf8')).hexdigest() +
                       '.record')

        pattern = None
        if ctx.args.path:
            pattern = '*%s*' % ctx.args.path.strip('*')

        record_cache = ctx.app.cache.getCache('baker')
        if not record_cache.has(record_name):
            raise Exception("No record has been created for this output path. "
                            "Did you bake there yet?")

        # Show the bake record.
        record = BakeRecord.load(record_cache.getCachePath(record_name))
        logging.info("Bake record for: %s" % record.out_dir)
        logging.info("Last baked: %s" %
                     datetime.datetime.fromtimestamp(record.bake_time))
        if record.success:
            logging.info("Status: success")
        else:
            logging.error("Status: failed")
        logging.info("Entries:")
        for entry in record.entries:
            if pattern:
                if not fnmatch.fnmatch(entry.rel_path, pattern):
                    continue
            logging.info(" - ")
            logging.info("   path:      %s" % entry.rel_path)
            logging.info("   spec:      %s:%s" % (entry.source_name,
                                                  entry.rel_path))
            logging.info("   taxonomy:  %s:%s" % (entry.taxonomy_name,
                                                  entry.taxonomy_term))
            logging.info("   config:    %s" % entry.config)
            logging.info("   out URLs:  %s" % entry.out_uris)
            logging.info("   out paths: %s" % [os.path.relpath(p, out_dir)
                                               for p in entry.out_paths])
            logging.info("   used srcs: %s" % entry.used_source_names)
            if entry.errors:
                logging.error("   errors: %s" % entry.errors)

        record_cache = ctx.app.cache.getCache('proc')
        if not record_cache.has(record_name):
            return

        # Show the pipeline record.
        record = ProcessorPipelineRecord.load(
                record_cache.getCachePath(record_name))
        logging.info("")
        logging.info("Processing record for: %s" % record.out_dir)
        logging.info("Last baked: %s" %
                     datetime.datetime.fromtimestamp(record.process_time))
        if record.success:
            logging.info("Status: success")
        else:
            logging.error("Status: failed")
        logging.info("Entries:")
        for entry in record.entries:
            if pattern:
                if not fnmatch.fnmatch(entry.rel_input, pattern):
                    continue
            flags = []
            if entry.flags & FLAG_PREPARED:
                flags.append('prepared')
            if entry.flags & FLAG_PROCESSED:
                flags.append('processed')
            if entry.flags & FLAG_OVERRIDEN:
                flags.append('overriden')
            if entry.flags & FLAG_BYPASSED_STRUCTURED_PROCESSING:
                flags.append('external')
            logger.info(" - ")
            logger.info("   path:      %s" % entry.rel_input)
            logger.info("   out paths: %s" % entry.rel_outputs)
            logger.info("   flags:     %s" % flags)
            logger.info("   proc tree: %s" % format_proc_tree(
                    entry.proc_tree, 14*' '))
            if entry.errors:
                logger.error("   errors: %s" % entry.errors)


def format_proc_tree(tree, margin='', level=0):
    name, children = tree
    res = '%s%s+ %s\n' % (margin if level > 0 else '', level * '  ', name)
    if children:
        for c in children:
            res += format_proc_tree(c, margin, level + 1)
    return res

