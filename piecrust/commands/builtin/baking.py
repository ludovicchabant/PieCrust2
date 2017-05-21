import time
import os.path
import logging
import fnmatch
import datetime
from colorama import Fore
from piecrust.commands.base import ChefCommand


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
            '-p', '--pipelines',
            help="The pipelines to run.",
            nargs='*')
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
            '--show-stats',
            help="Show detailed information about the bake.",
            action='store_true')

    def run(self, ctx):
        from piecrust.chefutil import format_timed

        out_dir = (ctx.args.output or
                   os.path.join(ctx.app.root_dir, '_counter'))

        start_time = time.perf_counter()
        try:
            records = self._doBake(ctx, out_dir)

            # Show merged stats.
            if ctx.args.show_stats:
                logger.info("-------------------")
                logger.info("Timing information:")
                _show_stats(records.stats)

            # All done.
            logger.info('-------------------------')
            logger.info(format_timed(start_time, 'done baking'))
            return 0 if records.success else 1
        except Exception as ex:
            if ctx.app.debug:
                logger.exception(ex)
            else:
                logger.error(str(ex))
            return 1

    def _doBake(self, ctx, out_dir):
        from piecrust.baking.baker import Baker

        if ctx.args.workers > 0:
            ctx.app.config.set('baker/workers', ctx.args.workers)
        if ctx.args.batch_size > 0:
            ctx.app.config.set('baker/batch_size', ctx.args.batch_size)

        allowed_pipelines = None
        if ctx.args.html_only:
            allowed_pipelines = ['page']
        elif ctx.args.assets_only:
            allowed_pipelines = ['asset']
        elif ctx.args.pipelines:
            allowed_pipelines = ctx.args.pipelines

        baker = Baker(
            ctx.appfactory, ctx.app, out_dir,
            force=ctx.args.force,
            allowed_pipelines=allowed_pipelines)
        records = baker.bake()

        return records


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
            '-i', '--in-path',
            help="A pattern that will be used to filter the relative path "
            "of entries to show.")
        parser.add_argument(
            '-t', '--out-path',
            help="A pattern that will be used to filter the output path "
            "of entries to show.")
        parser.add_argument(
            '--fails',
            action='store_true',
            help="Only show record entries for failures.")
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
        parser.add_argument(
            '-p', '--pipelines',
            nargs='*',
            help="Only show records for the given pipeline(s).")
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help="Show stats from the record.")
        parser.add_argument(
            '--show-manifest',
            help="Show manifest entries from the record.")

    def run(self, ctx):
        from piecrust.baking.baker import get_bake_records_path
        from piecrust.pipelines.records import load_records

        out_dir = ctx.args.output or os.path.join(ctx.app.root_dir, '_counter')
        suffix = '' if ctx.args.last == 0 else '.%d' % ctx.args.last
        records_path = get_bake_records_path(ctx.app, out_dir, suffix=suffix)
        records = load_records(records_path)
        if records.invalidated:
            raise Exception(
                "The bake record was saved by a previous version of "
                "PieCrust and can't be shown.")

        in_pattern = None
        if ctx.args.in_path:
            in_pattern = '*%s*' % ctx.args.in_path.strip('*')

        out_pattern = None
        if ctx.args.out_path:
            out_pattern = '*%s*' % ctx.args.out.strip('*')

        pipelines = ctx.args.pipelines
        if not pipelines:
            pipelines = [p.PIPELINE_NAME
                         for p in ctx.app.plugin_loader.getPipelines()]
        if ctx.args.assets_only:
            pipelines = ['asset']
        if ctx.args.html_only:
            pipelines = ['page']

        logger.info("Bake record for: %s" % out_dir)
        logger.info("Status: %s" % ('SUCCESS' if records.success
                                    else 'FAILURE'))
        logger.info("Date/time: %s" %
                    datetime.datetime.fromtimestamp(records.bake_time))
        logger.info("Incremental count: %d" % records.incremental_count)
        logger.info("Versions: %s/%s" % (records._app_version,
                                         records._record_version))
        logger.info("")

        for rec in records.records:
            if ctx.args.fails and rec.success:
                continue

            logger.info("Record: %s" % rec.name)
            logger.info("Status: %s" % ('SUCCESS' if rec.success
                                        else 'FAILURE'))
            for e in rec.entries:
                if ctx.args.fails and e.success:
                    continue
                if in_pattern and not fnmatch.fnmatch(e.item_spec, in_pattern):
                    continue
                if out_pattern and not any(
                        [fnmatch.fnmatch(op, out_pattern)
                         for op in e.out_paths]):
                    continue
                _print_record_entry(e)

            logger.info("")

        stats = records.stats
        if ctx.args.show_stats:
            _show_stats(stats)

        if ctx.args.show_manifest:
            for name in sorted(stats.manifests.keys()):
                if ctx.args.show_manifest.lower() in name.lower():
                    val = stats.manifests[name]
                    logger.info(
                        "    [%s%s%s] [%d entries]" %
                        (Fore.CYAN, name, Fore.RESET, len(val)))
                    for v in val:
                        logger.info("      - %s" % v)


def _show_stats(stats, *, full=False):
    indent = '    '

    logger.info('  Timers:')
    for name, val in sorted(stats.timers.items(), key=lambda i: i[1],
                            reverse=True):
        val_str = '%8.1f s' % val
        logger.info(
            "%s[%s%s%s] %s" %
            (indent, Fore.GREEN, val_str, Fore.RESET, name))

    logger.info('  Counters:')
    for name in sorted(stats.counters.keys()):
        val_str = '%8d  ' % stats.counters[name]
        logger.info(
            "%s[%s%s%s] %s" %
            (indent, Fore.GREEN, val_str, Fore.RESET, name))

    logger.info('  Manifests:')
    for name in sorted(stats.manifests.keys()):
        val = stats.manifests[name]
        logger.info(
            "%s[%s%s%s] [%d entries]" %
            (indent, Fore.CYAN, name, Fore.RESET, len(val)))
        if full:
            for v in val:
                logger.info("%s  - %s" % (indent, v))


def _print_record_entry(e):
    logger.info(" - %s" % e.item_spec)
    logger.info("   Outputs:")
    if e.out_paths:
        for op in e.out_paths:
            logger.info("    - %s" % op)
    else:
        logger.info("      <none>")

    e_desc = e.describe()
    for k in sorted(e_desc.keys()):
        logger.info("   %s: %s" % (k, e_desc[k]))

    if e.errors:
        logger.error("   Errors:")
        for err in e.errors:
            logger.error("    - %s" % err)
