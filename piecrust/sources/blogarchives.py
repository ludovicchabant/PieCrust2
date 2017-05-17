import logging
import datetime
from piecrust.chefutil import format_timed_scope
from piecrust.data.filters import PaginationFilter, IFilterClause
from piecrust.data.iterators import PageIterator
from piecrust.routing import RouteParameter
from piecrust.sources.base import ContentSource, GeneratedContentException


logger = logging.getLogger(__name__)


class BlogArchivesSource(ContentSource):
    SOURCE_NAME = 'blog_archives'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)

    def getContents(self, group):
        raise GeneratedContentException()

    def prepareRenderContext(self, ctx):
        ctx.pagination_source = self.source

        year = ctx.page.route_metadata.get('year')
        if year is None:
            raise Exception(
                "Can't find the archive year in the route metadata")
        if type(year) is not int:
            raise Exception(
                "The route for generator '%s' should specify an integer "
                "parameter for 'year'." % self.name)

        flt = PaginationFilter()
        flt.addClause(IsFromYearFilterClause(year))
        ctx.pagination_filter = flt

        ctx.custom_data['year'] = year

        flt2 = PaginationFilter()
        flt2.addClause(IsFromYearFilterClause(year))
        it = PageIterator(self.source, pagination_filter=flt2,
                          sorter=_date_sorter)
        ctx.custom_data['archives'] = it

    def bake(self, ctx):
        if not self.page_ref.exists:
            logger.debug(
                "No page found at '%s', skipping %s archives." %
                (self.page_ref, self.source_name))
            return

        logger.debug("Baking %s archives...", self.source_name)
        with format_timed_scope(logger, 'gathered archive years',
                                level=logging.DEBUG, colored=False):
            all_years, dirty_years = self._buildDirtyYears(ctx)

        with format_timed_scope(logger, "baked %d %s archives." %
                                (len(dirty_years), self.source_name)):
            self._bakeDirtyYears(ctx, all_years, dirty_years)

    def _getSource(self):
        return self.app.getSource(self.config['source'])

    def _buildDirtyYears(self, ctx):
        logger.debug("Gathering dirty post years.")
        all_years = set()
        dirty_years = set()
        for _, cur_entry in ctx.getAllPageRecords():
            if cur_entry and cur_entry.source_name == self.source_name:
                dt = datetime.datetime.fromtimestamp(cur_entry.timestamp)
                all_years.add(dt.year)
                if cur_entry.was_any_sub_baked:
                    dirty_years.add(dt.year)
        return all_years, dirty_years

    def _bakeDirtyYears(self, ctx, all_years, dirty_years):
        route = self.app.getGeneratorRoute(self.name)
        if route is None:
            raise Exception(
                "No routes have been defined for generator: %s" %
                self.name)

        logger.debug("Using archive page: %s" % self.page_ref)
        fac = self.page_ref.getFactory()

        for y in dirty_years:
            extra_route_metadata = {'year': y}

            logger.debug("Queuing: %s [%s]" % (fac.ref_spec, y))
            ctx.queueBakeJob(fac, route, extra_route_metadata, str(y))
        ctx.runJobQueue()

        # Create bake entries for the years that were *not* dirty.
        # Otherwise, when checking for deleted pages, we would not find any
        # outputs and would delete those files.
        all_str_years = [str(y) for y in all_years]
        for prev_entry, cur_entry in ctx.getAllPageRecords():
            if prev_entry and not cur_entry:
                try:
                    y = ctx.getSeedFromRecordExtraKey(prev_entry.extra_key)
                except InvalidRecordExtraKey:
                    continue
                if y in all_str_years:
                    logger.debug(
                        "Creating unbaked entry for year %s archive." % y)
                    ctx.collapseRecord(prev_entry)
                else:
                    logger.debug(
                        "No page references year %s anymore." % y)

    def getSupportedRouteParameters(self):
        return [RouteParameter('year', RouteParameter.TYPE_INT4)]


class IsFromYearFilterClause(IFilterClause):
    def __init__(self, year):
        self.year = year

    def pageMatches(self, fil, page):
        return (page.datetime.year == self.year)


def _date_sorter(it):
    return sorted(it, key=lambda x: x.datetime)

