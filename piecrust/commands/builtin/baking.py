import os.path
import time
import logging
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
            help="Specifies the pipelines to run.",
            action='append')
        parser.add_argument(
            '-s', '--sources',
            help="Specifies the content sources to run.",
            action='append')
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
        parser.add_argument(
            '--profile',
            help="Run the bake several times, for profiling.",
            type=int, default=-1)

    def run(self, ctx):
        from piecrust.chefutil import format_timed
        from piecrust.environment import ExecutionStats

        out_dir = (ctx.args.output or
                   os.path.join(ctx.app.root_dir, '_counter'))

        success = True
        avg_stats = ExecutionStats()
        avg_stats.registerTimer('Total')
        start_time = time.perf_counter()

        num_iter = 1
        if ctx.args.profile > 0:
            num_iter = ctx.args.profile

        for i in range(num_iter):
            iter_start_time = time.perf_counter()
            if num_iter > 1:
                import gc
                gc.collect()
                logger.info("---- %d/%d ----" % (i + 1, num_iter))
                # Don't cheat -- the app instance caches a bunch of stuff
                # so we need to create a fresh one.
                ctx.app = ctx.appfactory.create()

            try:
                records = self._doBake(ctx, out_dir)
            except Exception as ex:
                if ctx.app.debug:
                    logger.exception(ex)
                else:
                    logger.error(str(ex))
                return 1

            success = success and records.success
            avg_stats.mergeStats(records.stats)
            avg_stats.stepTimerSince('Total', iter_start_time)

        # Show merged stats.
        if ctx.args.show_stats:
            if num_iter > 1:
                _average_stats(avg_stats, num_iter)

            logger.info("-------------------")
            logger.info("Timing information:")
            _show_stats(avg_stats)

        # All done.
        logger.info('-------------------------')
        logger.info(format_timed(start_time, 'done baking'))
        return 0 if success else 1

    def _doBake(self, ctx, out_dir):
        from piecrust.baking.baker import Baker

        if ctx.args.workers > 0:
            ctx.app.config.set('baker/workers', ctx.args.workers)
        if ctx.args.batch_size > 0:
            ctx.app.config.set('baker/batch_size', ctx.args.batch_size)

        allowed_pipelines = None
        forbidden_pipelines = None
        if ctx.args.html_only:
            forbidden_pipelines = ['asset']
        elif ctx.args.assets_only:
            allowed_pipelines = ['asset']
        elif ctx.args.pipelines:
            if allowed_pipelines or forbidden_pipelines:
                raise Exception(
                    "Can't specify `--html-only` or `--assets-only` with "
                    "`--pipelines`.")
            allowed_pipelines = []
            forbidden_pipelines = []
            for p in ctx.args.pipelines:
                if p[0] == '-':
                    forbidden_pipelines.append(p)
                else:
                    allowed_pipelines.append(p)
            if not allowed_pipelines:
                allowed_pipelines = None
            if not forbidden_pipelines:
                forbidden_pipelines = None

        baker = Baker(
            ctx.appfactory, ctx.app, out_dir,
            force=ctx.args.force,
            allowed_sources=ctx.args.sources,
            allowed_pipelines=allowed_pipelines,
            forbidden_pipelines=forbidden_pipelines)
        records = baker.bake()

        return records


class ShowRecordCommand(ChefCommand):
    def __init__(self):
        super(ShowRecordCommand, self).__init__()
        self.name = 'showrecords'
        self.description = ("Shows the bake records for a given output "
                            "directory.")

    def setupParser(self, parser, app):
        parser.add_argument(
            '-o', '--output',
            help="The output directory for which to show the bake records "
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
            help="Show the last Nth bake records.")
        parser.add_argument(
            '--records',
            help="Load the specified records file.")
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
            help="Show stats from the records.")
        parser.add_argument(
            '--show-manifest',
            help="Show manifest entries from the records.")

    def run(self, ctx):
        import fnmatch
        from piecrust.baking.baker import get_bake_records_path
        from piecrust.pipelines.records import load_records

        records_path = ctx.args.records
        if records_path is None:
            out_dir = ctx.args.output or os.path.join(ctx.app.root_dir,
                                                      '_counter')
            suffix = '' if ctx.args.last == 0 else '.%d' % ctx.args.last
            records_path = get_bake_records_path(ctx.app, out_dir,
                                                 suffix=suffix)
            logger.info("Bake records for output: %s" % out_dir)
        else:
            logger.info("Bake records from: %s" % records_path)

        records = load_records(records_path, True)
        if records.invalidated:
            raise Exception(
                "The bake records were saved by a previous version of "
                "PieCrust and can't be shown.")

        in_pattern = None
        if ctx.args.in_path:
            in_pattern = '*%s*' % ctx.args.in_path.strip('*')

        out_pattern = None
        if ctx.args.out_path:
            out_pattern = '*%s*' % ctx.args.out_path.strip('*')

        pipelines = ctx.args.pipelines
        if pipelines is None:
            if ctx.args.assets_only:
                pipelines = ['asset']
            if ctx.args.html_only:
                pipelines = ['page']

        logger.info("Status: %s" % ('SUCCESS' if records.success
                                    else 'FAILURE'))
        logger.info("Date/time: %s" %
                    datetime.datetime.fromtimestamp(records.bake_time))
        logger.info("Incremental count: %d" % records.incremental_count)
        logger.info("Versions: %s/%s" % (records._app_version,
                                         records._record_version))
        logger.info("")

        if not ctx.args.show_stats and not ctx.args.show_manifest:
            for rec in sorted(records.records, key=lambda r: r.name):
                if ctx.args.fails and rec.success:
                    logger.debug(
                        "Ignoring record '%s' because it was successful, "
                        "and `--fail` was passed." % rec.name)
                    continue

                ppname = rec.name[rec.name.index('@') + 1:]
                if pipelines is not None and ppname not in pipelines:
                    logging.debug(
                        "Ignoring record '%s' because it was created by "
                        "pipeline '%s', which isn't listed in "
                        "`--pipelines`." % (rec.name, ppname))
                    continue

                entries_to_show = []

                for e in rec.getEntries():
                    if ctx.args.fails and e.success:
                        continue
                    if in_pattern and not fnmatch.fnmatch(e.item_spec,
                                                          in_pattern):
                        continue
                    if out_pattern and not any(
                            [fnmatch.fnmatch(op, out_pattern)
                             for op in e.getAllOutputPaths()]):
                        continue
                    entries_to_show.append(e)

                if entries_to_show:
                    logger.info("Record: %s" % rec.name)
                    logger.info("Status: %s" % ('SUCCESS' if rec.success
                                                else 'FAILURE'))
                    logger.info("User Data:")
                    if not rec.user_data:
                        logger.info("  <empty>")
                    else:
                        for k, v in rec.user_data.items():
                            logger.info("  %s: %s" % (k, v))

                    logger.info("Entries:")
                    for e in entries_to_show:
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


def _average_stats(stats, cnt):
    for name in stats.timers:
        stats.timers[name] /= cnt
    for name in stats.counters:
        stats.counters[name] /= cnt


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
    import pprint
    import textwrap

    logger.info(" - %s" % e.item_spec)
    logger.info("   Outputs:")
    out_paths = list(e.getAllOutputPaths())
    if out_paths:
        for op in out_paths:
            logger.info("    - %s" % op)
    else:
        logger.info("      <none>")

    e_desc = e.describe()
    for k, v in e_desc.items():
        if isinstance(v, dict):
            text = pprint.pformat(v, indent=2)
            logger.info("   %s:" % k)
            logger.info(textwrap.indent(text, '     '))
        else:
            logger.info("   %s: %s" % (k, v))

    errors = list(e.getAllErrors())
    if errors:
        logger.error("   Errors:")
        for err in errors:
            logger.error("    - %s" % err)
