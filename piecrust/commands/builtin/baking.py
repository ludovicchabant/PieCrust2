import time
import os.path
import logging
import hashlib
import fnmatch
import datetime
from colorama import Fore
from piecrust import CACHE_DIR
from piecrust.baking.baker import Baker
from piecrust.baking.records import (
        BakeRecord, BakeRecordEntry, SubPageBakeInfo)
from piecrust.chefutil import format_timed
from piecrust.commands.base import ChefCommand
from piecrust.processing.pipeline import ProcessorPipeline
from piecrust.processing.records import (
        ProcessorPipelineRecord,
        FLAG_PREPARED, FLAG_PROCESSED,
        FLAG_BYPASSED_STRUCTURED_PROCESSING)
from piecrust.rendering import (
        PASS_FORMATTING, PASS_RENDERING)


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
                '-w', '--workers',
                help="The number of worker processes to spawn.",
                type=int, default=-1)
        parser.add_argument(
                '--batch-size',
                help="The number of jobs per batch.",
                type=int, default=-1)
        parser.add_argument(
                '--assets-only',
                help="Only bake the assets (don't bake the web pages).",
                action='store_true')
        parser.add_argument(
                '--html-only',
                help="Only bake the pages (don't run the asset pipeline).",
                action='store_true')
        parser.add_argument(
                '--show-timers',
                help="Show detailed timing information.",
                action='store_true')
        parser.add_argument(
                '--foodtruck',
                help="Run the asset pipeline for FoodTruck.",
                action='store_true')

    def run(self, ctx):
        if ctx.args.foodtruck:
            if ctx.args.html_only:
                raise Exception("`--foodtruck` and `--html-only` can't be "
                                "both specified.")
            if ctx.args.output:
                raise Exception("`--foodtruck` and `--output` can't be "
                                "both specified.")

            ctx.args.assets_only = True
            ctx.args.output = os.path.join(ctx.app.root_dir, CACHE_DIR,
                                           'foodtruck', 'server')

        out_dir = (ctx.args.output or
                   os.path.join(ctx.app.root_dir, '_counter'))

        success = True
        ctx.timers = {}
        start_time = time.perf_counter()
        try:
            # Bake the site sources.
            if not ctx.args.assets_only:
                success = success & self._bakeSources(ctx, out_dir)

            # Bake the assets.
            if not ctx.args.html_only:
                success = success & self._bakeAssets(ctx, out_dir)

            # Show merged timers.
            if ctx.args.show_timers:
                logger.info("-------------------")
                logger.info("Timing information:")
                _show_timers(ctx.timers)

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
        if ctx.args.workers > 0:
            ctx.app.config.set('baker/workers', ctx.args.workers)
        if ctx.args.batch_size > 0:
            ctx.app.config.set('baker/batch_size', ctx.args.batch_size)
        baker = Baker(
                ctx.app, out_dir,
                force=ctx.args.force,
                applied_config_variant=ctx.config_variant,
                applied_config_values=ctx.config_values)
        record = baker.bake()
        _merge_timers(record.timers, ctx.timers)
        return record.success

    def _bakeAssets(self, ctx, out_dir):
        proc = ProcessorPipeline(
                ctx.app, out_dir,
                force=ctx.args.force)
        record = proc.run()
        _merge_timers(record.timers, ctx.timers)
        return record.success


def _merge_timers(source, target):
    if source is None:
        return

    for name, val in source.items():
        if isinstance(val, float):
            if name not in target:
                target[name] = 0
            target[name] += val
        elif isinstance(val, dict):
            if name not in target:
                target[name] = {}
            _merge_timers(val, target[name])


def _show_timers(timers, indent=''):
    sub_timer_names = []
    for name in sorted(timers.keys()):
        if isinstance(timers[name], float):
            val_str = '%8.1f s' % timers[name]
            logger.info(
                    "%s[%s%s%s] %s" %
                    (indent, Fore.GREEN, val_str, Fore.RESET, name))
        else:
            sub_timer_names.append(name)

    for name in sub_timer_names:
        logger.info('%s:' % name)
        _show_timers(timers[name], indent + '  ')


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
        parser.add_argument(
                '-t', '--out',
                help="A pattern that will be used to filter the output path "
                     "of entries to show.")
        parser.add_argument(
                '--last',
                type=int,
                default=0,
                help="Show the last Nth bake record.")
        parser.add_argument(
                '--html-only',
                action='store_true',
                help="Only show records for pages (not from the asset "
                     "pipeline).")
        parser.add_argument(
                '--assets-only',
                action='store_true',
                help="Only show records for assets (not from pages).")

    def run(self, ctx):
        out_dir = ctx.args.output or os.path.join(ctx.app.root_dir, '_counter')
        record_id = hashlib.md5(out_dir.encode('utf8')).hexdigest()
        suffix = '' if ctx.args.last == 0 else '.%d' % ctx.args.last
        record_name = '%s%s.record' % (record_id, suffix)

        pattern = None
        if ctx.args.path:
            pattern = '*%s*' % ctx.args.path.strip('*')

        out_pattern = None
        if ctx.args.out:
            out_pattern = '*%s*' % ctx.args.out.strip('*')

        if not ctx.args.assets_only:
            self._showBakeRecord(ctx, record_name, pattern, out_pattern)
        if not ctx.args.html_only:
            self._showProcessingRecord(ctx, record_name, pattern, out_pattern)

    def _showBakeRecord(self, ctx, record_name, pattern, out_pattern):
        # Show the bake record.
        record_cache = ctx.app.cache.getCache('baker')
        if not record_cache.has(record_name):
            raise Exception("No record has been created for this output path. "
                            "Did you bake there yet?")

        record = BakeRecord.load(record_cache.getCachePath(record_name))
        logging.info("Bake record for: %s" % record.out_dir)
        logging.info("From: %s" % record_name)
        logging.info("Last baked: %s" %
                     datetime.datetime.fromtimestamp(record.bake_time))
        if record.success:
            logging.info("Status: success")
        else:
            logging.error("Status: failed")
        logging.info("Entries:")
        for entry in record.entries:
            if pattern and not fnmatch.fnmatch(entry.path, pattern):
                continue
            if out_pattern and not (
                    any([o for o in entry.out_paths
                         if fnmatch.fnmatch(o, out_pattern)])):
                continue

            flags = _get_flag_descriptions(
                    entry.flags,
                    {
                        BakeRecordEntry.FLAG_NEW: 'new',
                        BakeRecordEntry.FLAG_SOURCE_MODIFIED: 'modified',
                        BakeRecordEntry.FLAG_OVERRIDEN: 'overriden'})

            logging.info(" - ")

            rel_path = os.path.relpath(entry.path, ctx.app.root_dir)
            logging.info("   path:      %s" % rel_path)
            logging.info("   source:    %s" % entry.source_name)
            if entry.taxonomy_info:
                ti = entry.taxonomy_info
                logging.info("   taxonomy:  %s = %s (in %s)" %
                             (ti.taxonomy_name, ti.term, ti.source_name))
            else:
                logging.info("   taxonomy:  <none>")
            logging.info("   flags:     %s" % _join(flags))
            logging.info("   config:    %s" % entry.config)

            if entry.errors:
                logging.error("   errors: %s" % entry.errors)

            logging.info("   %d sub-pages:" % len(entry.subs))
            for sub in entry.subs:
                sub_flags = _get_flag_descriptions(
                        sub.flags,
                        {
                            SubPageBakeInfo.FLAG_BAKED: 'baked',
                            SubPageBakeInfo.FLAG_FORCED_BY_SOURCE:
                                'forced by source',
                            SubPageBakeInfo.FLAG_FORCED_BY_NO_PREVIOUS:
                                'forced by missing previous record entry',
                            SubPageBakeInfo.FLAG_FORCED_BY_PREVIOUS_ERRORS:
                                'forced by previous errors',
                            SubPageBakeInfo.FLAG_FORMATTING_INVALIDATED:
                                'formatting invalidated'})

                logging.info("   - ")
                logging.info("     URL:    %s" % sub.out_uri)
                logging.info("     path:   %s" % os.path.relpath(
                        sub.out_path, record.out_dir))
                logging.info("     flags:  %s" % _join(sub_flags))

                if sub.render_info:
                    pass_names = {
                            PASS_FORMATTING: 'formatting pass',
                            PASS_RENDERING: 'rendering pass'}
                    for p, ri in sub.render_info.items():
                        logging.info("     - %s" % pass_names[p])
                        logging.info("       used sources:  %s" %
                                     _join(ri.used_source_names))
                        pgn_info = 'no'
                        if ri.used_pagination:
                            pgn_info = 'yes'
                        if ri.pagination_has_more:
                            pgn_info += ', has more'
                        logging.info("       used pagination: %s", pgn_info)
                        logging.info("       used assets: %s",
                                     'yes' if ri.used_assets else 'no')
                        logging.info("       used terms: %s" %
                                     _join(
                                            ['%s=%s (%s)' % (tn, t, sn)
                                             for sn, tn, t in
                                             ri.used_taxonomy_terms]))
                else:
                    logging.info("     no render info")

                if sub.errors:
                    logging.error("   errors: %s" % sub.errors)

    def _showProcessingRecord(self, ctx, record_name, pattern, out_pattern):
        record_cache = ctx.app.cache.getCache('proc')
        if not record_cache.has(record_name):
            raise Exception("No record has been created for this output path. "
                            "Did you bake there yet?")

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
            rel_path = os.path.relpath(entry.path, ctx.app.root_dir)
            if pattern and not fnmatch.fnmatch(rel_path, pattern):
                continue
            if out_pattern and not (
                    any([o for o in entry.rel_outputs
                         if fnmatch.fnmatch(o, out_pattern)])):
                continue

            flags = _get_flag_descriptions(
                    entry.flags,
                    {
                        FLAG_PREPARED: 'prepared',
                        FLAG_PROCESSED: 'processed',
                        FLAG_BYPASSED_STRUCTURED_PROCESSING: 'external'})

            logger.info(" - ")
            logger.info("   path:      %s" % rel_path)
            logger.info("   out paths: %s" % entry.rel_outputs)
            logger.info("   flags:     %s" % _join(flags))
            logger.info("   proc tree: %s" % _format_proc_tree(
                    entry.proc_tree, 14*' '))

            if entry.errors:
                logger.error("   errors: %s" % entry.errors)


def _join(items, sep=', ', text_if_none='none'):
    if items:
        return sep.join(items)
    return text_if_none


def _get_flag_descriptions(flags, descriptions):
    res = []
    for k, v in descriptions.items():
        if flags & k:
            res.append(v)
    return res


def _format_proc_tree(tree, margin='', level=0):
    name, children = tree
    res = '%s%s+ %s\n' % (margin if level > 0 else '', level * '  ', name)
    if children:
        for c in children:
            res += _format_proc_tree(c, margin, level + 1)
    return res

