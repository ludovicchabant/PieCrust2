import time
import logging
import datetime
import collections
from piecrust.data.filters import PaginationFilter, IFilterClause
from piecrust.dataproviders.pageiterator import (
    PageIterator, HardCodedFilterIterator, DateSortIterator)
from piecrust.page import Page
from piecrust.pipelines._pagebaker import PageBaker
from piecrust.pipelines._pagerecords import PagePipelineRecordEntry
from piecrust.pipelines.base import (
    ContentPipeline,
    create_job, get_record_name_for_source)
from piecrust.routing import RouteParameter
from piecrust.sources.base import ContentItem
from piecrust.sources.generator import GeneratorSourceBase
from piecrust.sources.list import ListSource


logger = logging.getLogger(__name__)


_year_index = """---
layout: %(template)s
---
"""


class BlogArchivesSource(GeneratorSourceBase):
    SOURCE_NAME = 'blog_archives'
    DEFAULT_PIPELINE_NAME = 'blog_archives'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)

        tpl_name = config.get('template', '_year.html')
        self._raw_item = _year_index % {'template': tpl_name}

    def getSupportedRouteParameters(self):
        return [RouteParameter('year', RouteParameter.TYPE_INT4)]

    def findContentFromRoute(self, route_params):
        year = route_params['year']
        return ContentItem(
            '_index',
            {'route_params': {'year': year}})

    def prepareRenderContext(self, ctx):
        ctx.pagination_source = self.inner_source

        route_params = ctx.page.source_metadata['route_params']
        year = route_params.get('year')
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
        it = PageIterator(self.inner_source)
        it._simpleNonSortedWrap(HardCodedFilterIterator, flt2)
        it._wrapAsSort(DateSortIterator, reverse=False)
        ctx.custom_data['archives'] = it

        ctx.custom_data['monthly_archives'] = _MonthlyArchiveData(
            self.inner_source, year)


class IsFromYearFilterClause(IFilterClause):
    def __init__(self, year):
        self.year = year

    def pageMatches(self, fil, page):
        return (page.datetime.year == self.year)


class _MonthlyArchiveData(collections.abc.Mapping):
    def __init__(self, inner_source, year):
        self._inner_source = inner_source
        self._year = year
        self._months = None

    def __iter__(self):
        self._load()
        return iter(self._months)

    def __len__(self):
        self._load()
        return len(self._months)

    def __getitem__(self, i):
        self._load()
        return self._months[i]

    def _load(self):
        if self._months is not None:
            return

        month_index = {}
        for page in self._inner_source.getAllPages():
            if page.datetime.year != self._year:
                continue

            month = page.datetime.month

            posts_this_month = month_index.get(month)
            if posts_this_month is None:
                posts_this_month = []
                month_index[month] = posts_this_month
            posts_this_month.append(page.content_item)

        self._months = []
        for m in sorted(month_index.keys()):
            timestamp = time.mktime((self._year, m, 1, 0, 0, 0, 0, 0, -1))

            ptm = month_index[m]
            it = PageIterator(ListSource(self._inner_source, ptm))
            it._wrapAsSort(DateSortIterator, reverse=False)

            self._months.append({
                'timestamp': timestamp,
                'posts': it
            })


class BlogArchivesPipelineRecordEntry(PagePipelineRecordEntry):
    def __init__(self):
        super().__init__()
        self.year = None


class BlogArchivesPipeline(ContentPipeline):
    PIPELINE_NAME = 'blog_archives'
    PASS_NUM = 10
    RECORD_ENTRY_CLASS = BlogArchivesPipelineRecordEntry

    def __init__(self, source, ctx):
        if not isinstance(source, BlogArchivesSource):
            raise Exception("The blog archives pipeline only supports blog "
                            "archives content sources.")

        super().__init__(source, ctx)
        self.inner_source = source.inner_source
        self._tpl_name = source.config['template']
        self._all_years = None
        self._dirty_years = None
        self._pagebaker = None

    def initialize(self):
        self._pagebaker = PageBaker(self.app,
                                    self.ctx.out_dir,
                                    force=self.ctx.force)
        self._pagebaker.startWriterQueue()

    def shutdown(self):
        self._pagebaker.stopWriterQueue()

    def createJobs(self, ctx):
        logger.debug("Caching template page for blog archives '%s'." %
                     self.inner_source.name)
        page = self.app.getPage(self.source, ContentItem('_index', {}))
        page._load()

        logger.debug("Building blog archives for: %s" %
                     self.inner_source.name)
        self._buildDirtyYears(ctx)
        logger.debug("Got %d dirty years out of %d." %
                     (len(self._dirty_years), len(self._all_years)))

        jobs = []
        rec_fac = self.createRecordEntry
        current_record = ctx.current_record

        for y in self._dirty_years:
            record_entry_spec = '_index[%04d]' % y

            jobs.append(create_job(self, '_index',
                                   year=y,
                                   record_entry_spec=record_entry_spec))

            entry = rec_fac(record_entry_spec)
            current_record.addEntry(entry)

        if len(jobs) > 0:
            return jobs, "archive"
        return None, None

    def run(self, job, ctx, result):
        year = job['year']
        content_item = ContentItem('_index',
                                   {'year': year,
                                    'route_params': {'year': year}})
        page = Page(self.source, content_item)

        prev_entry = ctx.previous_entry
        rdr_subs = self._pagebaker.bake(page, prev_entry)

        result['subs'] = rdr_subs
        result['year'] = page.source_metadata['year']

    def handleJobResult(self, result, ctx):
        existing = ctx.record_entry
        existing.subs = result['subs']
        existing.year = result['year']

    def postJobRun(self, ctx):
        # Create bake entries for the years that were *not* dirty.
        # Otherwise, when checking for deleted pages, we would not find any
        # outputs and would delete those files.
        all_str_years = [str(y) for y in self._all_years]
        for prev, cur in ctx.record_history.diffs:
            if prev and not cur:
                y = prev.year
                if y in all_str_years:
                    logger.debug(
                        "Creating unbaked entry for year %s archive." % y)
                    cur.year = y
                    cur.out_paths = list(prev.out_paths)
                    cur.errors = list(prev.errors)
                else:
                    logger.debug(
                        "No page references year %s anymore." % y)

    def _buildDirtyYears(self, ctx):
        all_years = set()
        dirty_years = set()

        record_name = get_record_name_for_source(self.inner_source)
        current_records = ctx.record_histories.current
        cur_rec = current_records.getRecord(record_name)
        for cur_entry in cur_rec.getEntries():
            dt = datetime.datetime.fromtimestamp(cur_entry.timestamp)
            all_years.add(dt.year)
            if cur_entry.hasFlag(
                    PagePipelineRecordEntry.FLAG_SEGMENTS_RENDERED):
                dirty_years.add(dt.year)

        self._all_years = all_years
        self._dirty_years = dirty_years

