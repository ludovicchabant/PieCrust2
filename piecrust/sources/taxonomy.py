import re
import logging
import unidecode
from piecrust.configuration import ConfigurationError
from piecrust.data.filters import (
    PaginationFilter, SettingFilterClause)
from piecrust.page import Page
from piecrust.pipelines._pagebaker import PageBaker
from piecrust.pipelines._pagerecords import PagePipelineRecordEntry
from piecrust.pipelines.base import (
    ContentPipeline, get_record_name_for_source)
from piecrust.pipelines.records import RecordHistory
from piecrust.routing import RouteParameter
from piecrust.sources.base import ContentItem
from piecrust.sources.generator import GeneratorSourceBase


logger = logging.getLogger(__name__)


SLUGIFY_ENCODE = 1
SLUGIFY_TRANSLITERATE = 2
SLUGIFY_LOWERCASE = 4
SLUGIFY_DOT_TO_DASH = 8
SLUGIFY_SPACE_TO_DASH = 16


re_first_dot_to_dash = re.compile(r'^\.+')
re_dot_to_dash = re.compile(r'\.+')
re_space_to_dash = re.compile(r'\s+')


class Taxonomy(object):
    """ Describes a taxonomy.
    """
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.term_name = config.get('term', name)
        self.is_multiple = bool(config.get('multiple', False))
        self.separator = config.get('separator', '/')
        self.page_ref = config.get('page')

    @property
    def setting_name(self):
        if self.is_multiple:
            return self.name
        return self.term_name


_taxonomy_index = """---
layout: %(template)s
---
"""


class TaxonomySource(GeneratorSourceBase):
    """ A content source that generates taxonomy listing pages.
    """
    SOURCE_NAME = 'taxonomy'
    DEFAULT_PIPELINE_NAME = 'taxonomy'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)

        tax_name = config.get('taxonomy')
        if tax_name is None:
            raise ConfigurationError(
                "Taxonomy source '%s' requires a taxonomy name." % name)
        self.taxonomy = _get_taxonomy(app, tax_name)

        sm = config.get('slugify_mode')
        self.slugifier = _get_slugifier(app, self.taxonomy, sm)

        tpl_name = config.get('template', '_%s.html' % tax_name)
        self._raw_item = _taxonomy_index % {'template': tpl_name}

    def getSupportedRouteParameters(self):
        name = self.taxonomy.term_name
        param_type = (RouteParameter.TYPE_PATH if self.taxonomy.is_multiple
                      else RouteParameter.TYPE_STRING)
        return [RouteParameter(name, param_type,
                               variadic=self.taxonomy.is_multiple)]

    def findContent(self, route_params):
        slugified_term = route_params[self.taxonomy.term_name]
        spec = '_index'
        metadata = {'term': slugified_term,
                    'record_entry_spec': '_index[%s]' % slugified_term,
                    'route_params': {
                        self.taxonomy.term_name: slugified_term}
                    }
        return ContentItem(spec, metadata)

    def slugify(self, term):
        return self.slugifier.slugify(term)

    def slugifyMultiple(self, terms):
        return self.slugifier.slugifyMultiple(terms)

    def prepareRenderContext(self, ctx):
        # Set the pagination source as the source we're generating for.
        ctx.pagination_source = self.inner_source

        # Get the taxonomy terms from the route metadata... this can come from
        # the browser's URL (while serving) or from the baking (see `bake`
        # method below). In both cases, we expect to have the *slugified*
        # version of the term, because we're going to set a filter that also
        # slugifies the terms found on each page.
        #
        # This is because:
        #  * while serving, we get everything from the request URL, so we only
        #    have the slugified version.
        #  * if 2 slightly different terms "collide" into the same slugified
        #    term, we'll get a merge of the 2 on the listing page, which is
        #    what the user expects.
        #
        route_params = ctx.page.source_metadata['route_params']
        tax_terms, is_combination = self._getTaxonomyTerms(route_params)
        self._setTaxonomyFilter(ctx, tax_terms, is_combination)

        # Add some custom data for rendering.
        ctx.custom_data.update({
            self.taxonomy.term_name: tax_terms,
            'is_multiple_%s' % self.taxonomy.term_name: is_combination})
        # Add some "plural" version of the term... so for instance, if this
        # is the "tags" taxonomy, "tag" will have one term most of the time,
        # except when it's a combination. Here, we add "tags" as something that
        # is always a tuple, even when it's not a combination.
        if (self.taxonomy.is_multiple and
                self.taxonomy.name != self.taxonomy.term_name):
            mult_val = tax_terms
            if not is_combination:
                mult_val = (mult_val,)
            ctx.custom_data[self.taxonomy.name] = mult_val

    def _getTaxonomyTerms(self, route_params):
        # Get the individual slugified terms from the route metadata.
        all_values = route_params.get(self.taxonomy.term_name)
        if all_values is None:
            raise Exception("'%s' values couldn't be found in route metadata" %
                            self.taxonomy.term_name)

        # If it's a "multiple" taxonomy, we need to potentially split the
        # route value into the individual terms (_e.g._ when listing all pages
        # that have 2 given tags, we need to get each of those 2 tags).
        if self.taxonomy.is_multiple:
            sep = self.taxonomy.separator
            if sep in all_values:
                return tuple(all_values.split(sep)), True
        # Not a "multiple" taxonomy, so there's only the one value.
        return all_values, False

    def _setTaxonomyFilter(self, ctx, term_value, is_combination):
        # Set up the filter that will check the pages' terms.
        flt = PaginationFilter()
        flt.addClause(HasTaxonomyTermsFilterClause(
            self.taxonomy, self.slugifier.mode, term_value, is_combination))
        ctx.pagination_filter = flt

    def onRouteFunctionUsed(self, route_params):
        # Get the values, and slugify them appropriately.
        values = route_params[self.taxonomy.term_name]
        if self.taxonomy.is_multiple:
            # TODO: here we assume the route has been properly configured.
            slugified_values = self.slugifyMultiple((str(v) for v in values))
            route_val = self.taxonomy.separator.join(slugified_values)
        else:
            slugified_values = self.slugify(str(values))
            route_val = slugified_values

        # We need to register this use of a taxonomy term.
        rcs = self.app.env.render_ctx_stack
        cpi = rcs.current_ctx.current_pass_info
        if cpi:
            utt = cpi.getCustomInfo('used_taxonomy_terms', [], True)
            utt.append(slugified_values)

        # Put the slugified values in the route metadata so they're used to
        # generate the URL.
        route_params[self.taxonomy.term_name] = route_val


class HasTaxonomyTermsFilterClause(SettingFilterClause):
    def __init__(self, taxonomy, slugify_mode, value, is_combination):
        super().__init__(taxonomy.setting_name, value)
        self._taxonomy = taxonomy
        self._is_combination = is_combination
        self._slugifier = _Slugifier(taxonomy, slugify_mode)
        if taxonomy.is_multiple:
            self.pageMatches = self._pageMatchesAny
        else:
            self.pageMatches = self._pageMatchesSingle

    def _pageMatchesAny(self, fil, page):
        # Multiple taxonomy, i.e. it supports multiple terms, like tags.
        page_values = page.config.get(self.name)
        if page_values is None or not isinstance(page_values, list):
            return False

        page_set = set(map(self._slugifier.slugify, page_values))
        if self._is_combination:
            # Multiple taxonomy, and multiple terms to match. Check that
            # the ones to match are all in the page's terms.
            value_set = set(self.value)
            return value_set.issubset(page_set)
        else:
            # Multiple taxonomy, one term to match.
            return self.value in page_set

    def _pageMatchesSingle(self, fil, page):
        # Single taxonomy. Just compare the values.
        page_value = page.config.get(self.name)
        if page_value is None:
            return False
        page_value = self._slugifier.slugify(page_value)
        return page_value == self.value


def _get_taxonomy(app, tax_name):
    tax_config = app.config.get('site/taxonomies/' + tax_name)
    if tax_config is None:
        raise ConfigurationError("No such taxonomy: %s" % tax_name)
    return Taxonomy(tax_name, tax_config)


def _get_slugifier(app, taxonomy, slugify_mode=None):
    if slugify_mode is None:
        slugify_mode = app.config.get('site/slugify_mode', 'encode')
    sm = _parse_slugify_mode(slugify_mode)
    return _Slugifier(taxonomy, sm)


class TaxonomyPipelineRecordEntry(PagePipelineRecordEntry):
    def __init__(self):
        super().__init__()
        self.term = None


class TaxonomyPipeline(ContentPipeline):
    PIPELINE_NAME = 'taxonomy'
    PASS_NUM = 1
    RECORD_ENTRY_CLASS = TaxonomyPipelineRecordEntry

    def __init__(self, source, ctx):
        if not isinstance(source, TaxonomySource):
            raise Exception("The taxonomy pipeline only supports taxonomy "
                            "content sources.")

        super().__init__(source, ctx)
        self.inner_source = source.inner_source
        self.taxonomy = source.taxonomy
        self.slugifier = source.slugifier
        self._tpl_name = source.config['template']
        self._analyzer = None
        self._pagebaker = None

    def initialize(self):
        self._pagebaker = PageBaker(self.app,
                                    self.ctx.out_dir,
                                    force=self.ctx.force)
        self._pagebaker.startWriterQueue()

    def shutdown(self):
        self._pagebaker.stopWriterQueue()

    def createJobs(self, ctx):
        logger.debug("Caching template page for taxonomy '%s'." %
                     self.taxonomy.name)
        page = self.app.getPage(self.source, ContentItem('_index', {}))
        page._load()

        logger.debug("Building '%s' taxonomy pages for source: %s" %
                     (self.taxonomy.name, self.inner_source.name))
        self._analyzer = _TaxonomyTermsAnalyzer(self, ctx.record_histories)
        self._analyzer.analyze()

        logger.debug("Queuing %d '%s' jobs." %
                     (len(self._analyzer.dirty_slugified_terms),
                      self.taxonomy.name))
        jobs = []
        for slugified_term in self._analyzer.dirty_slugified_terms:
            item = ContentItem(
                '_index',
                {'term': slugified_term,
                 'record_entry_spec': '_index[%s]' % slugified_term,
                 'route_params': {
                     self.taxonomy.term_name: slugified_term}
                 })
            jobs.append(self.createJob(item))
        if len(jobs) > 0:
            return jobs
        return None

    def run(self, job, ctx, result):
        content_item = job.content_item
        logger.debug("Rendering '%s' page: %s" %
                     (self.taxonomy.name, content_item.metadata['term']))

        page = Page(self.source, job.content_item)
        prev_entry = ctx.previous_entry
        cur_entry = result.record_entry
        cur_entry.term = content_item.metadata['term']
        self._pagebaker.bake(page, prev_entry, cur_entry)

    def postJobRun(self, ctx):
        # We create bake entries for all the terms that were *not* dirty.
        # This is because otherwise, on the next incremental bake, we wouldn't
        # find any entry for those things, and figure that we need to delete
        # their outputs.
        analyzer = self._analyzer
        for prev, cur in ctx.record_history.diffs:
            # Only consider entries that don't have any current version
            # (i.e. they weren't baked just now).
            if prev and not cur:
                t = prev.term
                if analyzer.isKnownSlugifiedTerm(t):
                    logger.debug("Creating unbaked entry for '%s' term: %s" %
                                 (self.taxonomy.name, t))
                    cur.term = t
                    cur.out_paths = list(prev.out_paths)
                    cur.errors = list(prev.errors)
                else:
                    logger.debug("Term '%s' in '%s' isn't used anymore." %
                                 (t, self.taxonomy.name))


class _TaxonomyTermsAnalyzer(object):
    def __init__(self, pipeline, record_histories):
        self.pipeline = pipeline
        self.record_histories = record_histories
        self._all_terms = {}
        self._single_dirty_slugified_terms = set()
        self._all_dirty_slugified_terms = None

    @property
    def dirty_slugified_terms(self):
        """ Returns the slugified terms that have been 'dirtied' during
            this bake.
        """
        return self._all_dirty_slugified_terms

    def isKnownSlugifiedTerm(self, term):
        """ Returns whether the given slugified term has been seen during
            this bake.
        """
        return term in self._all_terms

    def analyze(self):
        # Build the list of terms for our taxonomy, and figure out which ones
        # are 'dirty' for the current bake.
        #
        # Remember all terms used.
        source = self.pipeline.inner_source
        taxonomy = self.pipeline.taxonomy
        slugifier = self.pipeline.slugifier

        record_name = get_record_name_for_source(source)
        current_records = self.record_histories.current
        cur_rec = current_records.getRecord(record_name)
        for cur_entry in cur_rec.getEntries():
            if not cur_entry.was_overriden:
                cur_terms = cur_entry.config.get(taxonomy.setting_name)
                if cur_terms:
                    if not taxonomy.is_multiple:
                        self._addTerm(
                            slugifier, cur_entry.item_spec, cur_terms)
                    else:
                        self._addTerms(
                            slugifier, cur_entry.item_spec, cur_terms)

        # Re-bake all taxonomy terms that include new or changed pages, by
        # marking them as 'dirty'.
        previous_records = self.record_histories.previous
        prev_rec = previous_records.getRecord(record_name)
        history = RecordHistory(prev_rec, cur_rec)
        history.build()
        for prev_entry, cur_entry in history.diffs:
            entries = [cur_entry]
            if prev_entry:
                entries.append(prev_entry)

            for e in entries:
                entry_terms = e.config.get(taxonomy.setting_name)
                if entry_terms:
                    if not taxonomy.is_multiple:
                        self._single_dirty_slugified_terms.add(
                            slugifier.slugify(entry_terms))
                    else:
                        self._single_dirty_slugified_terms.update(
                            (slugifier.slugify(t)
                             for t in entry_terms))

        self._all_dirty_slugified_terms = list(
            self._single_dirty_slugified_terms)
        logger.debug("Gathered %d dirty taxonomy terms",
                     len(self._all_dirty_slugified_terms))

        # Re-bake the combination pages for terms that are 'dirty'.
        # We make all terms into tuple, even those that are not actual
        # combinations, so that we have less things to test further down the
        # line.
        #
        # Add the combinations to that list. We get those combinations from
        # wherever combinations were used, so they're coming from the
        # `onRouteFunctionUsed` method.
        if taxonomy.is_multiple:
            known_combinations = set()
            for cur_entry in cur_rec.getEntries():
                used_terms = _get_all_entry_taxonomy_terms(cur_entry)
                for terms in used_terms:
                    if len(terms) > 1:
                        known_combinations.add(terms)

            dcc = 0
            for terms in known_combinations:
                if not self._single_dirty_slugified_terms.isdisjoint(
                        set(terms)):
                    self._all_dirty_slugified_terms.append(
                        taxonomy.separator.join(terms))
                    dcc += 1
            logger.debug("Gathered %d term combinations, with %d dirty." %
                         (len(known_combinations), dcc))

    def _addTerms(self, slugifier, item_spec, terms):
        for t in terms:
            self._addTerm(slugifier, item_spec, t)

    def _addTerm(self, slugifier, item_spec, term):
        st = slugifier.slugify(term)
        orig_terms = self._all_terms.setdefault(st, [])
        if orig_terms and orig_terms[0] != term:
            logger.warning(
                "Term '%s' in '%s' is slugified to '%s' which conflicts with "
                "previously existing '%s'. The two will be merged." %
                (term, item_spec, st, orig_terms[0]))
        orig_terms.append(term)


def _get_all_entry_taxonomy_terms(entry):
    res = set()
    for o in entry.subs:
        for pinfo in o.render_info:
            if pinfo:
                terms = pinfo.getCustomInfo('used_taxonomy_terms')
                if terms:
                    res |= set(terms)
    return res


class _Slugifier(object):
    def __init__(self, taxonomy, mode):
        self.taxonomy = taxonomy
        self.mode = mode

    def slugifyMultiple(self, terms):
        return tuple(map(self.slugify, terms))

    def slugify(self, term):
        if self.mode & SLUGIFY_TRANSLITERATE:
            term = unidecode.unidecode(term)
        if self.mode & SLUGIFY_LOWERCASE:
            term = term.lower()
        if self.mode & SLUGIFY_DOT_TO_DASH:
            term = re_first_dot_to_dash.sub('', term)
            term = re_dot_to_dash.sub('-', term)
        if self.mode & SLUGIFY_SPACE_TO_DASH:
            term = re_space_to_dash.sub('-', term)
        return term


def _parse_slugify_mode(value):
    mapping = {
        'encode': SLUGIFY_ENCODE,
        'transliterate': SLUGIFY_TRANSLITERATE,
        'lowercase': SLUGIFY_LOWERCASE,
        'dot_to_dash': SLUGIFY_DOT_TO_DASH,
        'space_to_dash': SLUGIFY_SPACE_TO_DASH}
    mode = 0
    for v in value.split(','):
        f = mapping.get(v.strip())
        if f is None:
            if v == 'iconv':
                raise Exception("'iconv' is not supported as a slugify mode "
                                "in PieCrust2. Use 'transliterate'.")
            raise Exception("Unknown slugify flag: %s" % v)
        mode |= f
    return mode

