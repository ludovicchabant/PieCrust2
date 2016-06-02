import re
import time
import logging
import unidecode
from piecrust.chefutil import format_timed, format_timed_scope
from piecrust.configuration import ConfigurationError
from piecrust.data.filters import (
        PaginationFilter, SettingFilterClause,
        page_value_accessor)
from piecrust.generation.base import PageGenerator, InvalidRecordExtraKey
from piecrust.sources.pageref import PageRef, PageNotFoundError


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
    def __init__(self, name, config):
        self.name = name
        self.config = config
        self.term_name = config.get('term', name)
        self.is_multiple = bool(config.get('multiple', False))
        self.separator = config.get('separator', '/')
        self.page_ref = config.get('page')
        self._source_page_refs = {}

    @property
    def setting_name(self):
        if self.is_multiple:
            return self.name
        return self.term_name


class TaxonomyPageGenerator(PageGenerator):
    GENERATOR_NAME = 'taxonomy'

    def __init__(self, app, name, config):
        super(TaxonomyPageGenerator, self).__init__(app, name, config)

        tax_name = config.get('taxonomy')
        if tax_name is None:
            raise ConfigurationError(
                    "Generator '%s' requires a taxonomy name." % name)
        tax_config = app.config.get('site/taxonomies/' + tax_name)
        if tax_config is None:
            raise ConfigurationError(
                    "Error initializing generator '%s', no such taxonomy: %s",
                    (name, tax_name))
        self.taxonomy = Taxonomy(tax_name, tax_config)

        sm = config.get('slugify_mode')
        if not sm:
            sm = app.config.get('site/slugify_mode', 'encode')
        self.slugify_mode = _parse_slugify_mode(sm)

    def prepareRenderContext(self, ctx):
        self._setPaginationSource(ctx)

        tax_terms, is_combination = self._getTaxonomyTerms(
                ctx.page.route_metadata)
        self._setTaxonomyFilter(ctx, tax_terms, is_combination)

        ctx.custom_data.update({
                self.taxonomy.term_name: tax_terms,
                'is_multiple_%s' % self.taxonomy.term_name: is_combination})
        if (self.taxonomy.is_multiple and
                self.taxonomy.name != self.taxonomy.term_name):
            mult_val = tax_terms
            if not is_combination:
                mult_val = (mult_val,)
            ctx.custom_data[self.taxonomy.name] = mult_val
        logger.debug("Prepared render context with: %s" % ctx.custom_data)

    def _getTaxonomyTerms(self, route_metadata):
        all_values = route_metadata.get(self.taxonomy.term_name)
        if all_values is None:
            raise Exception("'%s' values couldn't be found in route metadata" %
                            self.taxonomy.term_name)

        if self.taxonomy.is_multiple:
            sep = self.taxonomy.separator
            if sep in all_values:
                return tuple(all_values.split(sep)), True
        return all_values, False

    def _setTaxonomyFilter(self, ctx, term_value, is_combination):
        flt = PaginationFilter(value_accessor=page_value_accessor)
        flt.addClause(HasTaxonomyTermsFilterClause(
                self.taxonomy, self.slugify_mode, term_value, is_combination))
        ctx.pagination_filter = flt

    def _setPaginationSource(self, ctx):
        ctx.pagination_source = self.source

    def onRouteFunctionUsed(self, route, route_metadata):
        # Get the values.
        values = route_metadata[self.taxonomy.term_name]
        if self.taxonomy.is_multiple:
            #TODO: here we assume the route has been properly configured.
            values = tuple([str(v) for v in values])
        else:
            values = (str(values),)

        # We need to register this use of a taxonomy term.
        eis = self.app.env.exec_info_stack
        cpi = eis.current_page_info.render_ctx.current_pass_info
        if cpi:
            utt = cpi.getCustomInfo('used_taxonomy_terms', [], True)
            utt.append(values)

        # We need to slugify the terms before they get transformed
        # into URL-bits.
        s = _Slugifier(self.taxonomy, self.slugify_mode)
        str_values = s.slugify(values)
        route_metadata[self.taxonomy.term_name] = str_values
        logger.debug("Changed route metadata to: %s" % route_metadata)

    def bake(self, ctx):
        if not self.page_ref.exists:
            logger.debug(
                    "No page found at '%s', skipping taxonomy '%s'." %
                    (self.page_ref, self.taxonomy.name))
            return

        logger.debug("Baking %s pages...", self.taxonomy.name)
        with format_timed_scope(logger, 'gathered taxonomy terms',
                                level=logging.DEBUG, colored=False):
            all_terms, dirty_terms = self._buildDirtyTaxonomyTerms(ctx)

        start_time = time.perf_counter()
        page_count = self._bakeTaxonomyTerms(ctx, all_terms, dirty_terms)
        if page_count > 0:
            logger.info(format_timed(
                start_time,
                "baked %d %s pages for %s." % (
                    page_count, self.taxonomy.term_name, self.source_name)))

    def _buildDirtyTaxonomyTerms(self, ctx):
        # Build the list of terms for our taxonomy, and figure out which ones
        # are 'dirty' for the current bake.
        logger.debug("Gathering dirty taxonomy terms")
        all_terms = set()
        single_dirty_terms = set()

        # Re-bake all taxonomy terms that include new or changed pages.
        for prev_entry, cur_entry in ctx.getBakedPageRecords():
            if cur_entry.source_name != self.source_name:
                continue

            entries = [cur_entry]
            if prev_entry:
                entries.append(prev_entry)

            terms = []
            for e in entries:
                entry_terms = e.config.get(self.taxonomy.setting_name)
                if entry_terms:
                    if not self.taxonomy.is_multiple:
                        terms.append(entry_terms)
                    else:
                        terms += entry_terms
            single_dirty_terms.update(terms)

        # Remember all terms used.
        for _, cur_entry in ctx.getAllPageRecords():
            if cur_entry and not cur_entry.was_overriden:
                cur_terms = cur_entry.config.get(self.taxonomy.setting_name)
                if cur_terms:
                    if not self.taxonomy.is_multiple:
                        all_terms.add(cur_terms)
                    else:
                        all_terms |= set(cur_terms)

        # Re-bake the combination pages for terms that are 'dirty'.
        # We make all terms into tuple, even those that are not actual
        # combinations, so that we have less things to test further down the
        # line.
        dirty_terms = [(t,) for t in single_dirty_terms]
        # Add the combinations to that list.
        if self.taxonomy.is_multiple:
            known_combinations = set()
            logger.debug("Gathering dirty term combinations")
            for _, cur_entry in ctx.getAllPageRecords():
                if cur_entry:
                    used_terms = _get_all_entry_taxonomy_terms(cur_entry)
                    for terms in used_terms:
                        if len(terms) > 1:
                            known_combinations.add(terms)

            for terms in known_combinations:
                if not single_dirty_terms.isdisjoint(set(terms)):
                    dirty_terms.append(terms)

        return all_terms, dirty_terms

    def _bakeTaxonomyTerms(self, ctx, all_terms, dirty_terms):
        # Start baking those terms.
        logger.debug(
                "Baking '%s' for source '%s': %s" %
                (self.taxonomy.name, self.source_name, dirty_terms))

        route = self.app.getGeneratorRoute(self.name)
        if route is None:
            raise Exception("No routes have been defined for generator: %s" %
                            self.name)

        logger.debug("Using taxonomy page: %s" % self.page_ref)
        fac = self.page_ref.getFactory()

        job_count = 0
        s = _Slugifier(self.taxonomy, self.slugify_mode)
        for term in dirty_terms:
            if not self.taxonomy.is_multiple:
                term = term[0]
            slugified_term = s.slugify(term)
            extra_route_metadata = {self.taxonomy.term_name: slugified_term}

            # Use the slugified term as the record extra key.
            logger.debug(
                    "Queuing: %s [%s=%s]" %
                    (fac.ref_spec, self.taxonomy.name, slugified_term))
            ctx.queueBakeJob(fac, route, extra_route_metadata, slugified_term)
            job_count += 1
        ctx.runJobQueue()

        # Now we create bake entries for all the terms that were *not* dirty.
        # This is because otherwise, on the next incremental bake, we wouldn't
        # find any entry for those things, and figure that we need to delete
        # their outputs.
        for prev_entry, cur_entry in ctx.getAllPageRecords():
            # Only consider taxonomy-related entries that don't have any
            # current version (i.e. they weren't baked just now).
            if prev_entry and not cur_entry:
                try:
                    t = ctx.getSeedFromRecordExtraKey(prev_entry.extra_key)
                except InvalidRecordExtraKey:
                    continue

                if t in all_terms:
                    logger.debug("Creating unbaked entry for %s term: %s" %
                                 (self.name, t))
                    ctx.collapseRecord(prev_entry)
                else:
                    logger.debug("Term %s in %s isn't used anymore." %
                                 (self.name, t))

        return job_count


def _get_all_entry_taxonomy_terms(entry):
    res = set()
    for o in entry.subs:
        for pinfo in o.render_info:
            if pinfo:
                terms = pinfo.getCustomInfo('used_taxonomy_terms')
                if terms:
                    res |= set(terms)
    return res


class HasTaxonomyTermsFilterClause(SettingFilterClause):
    def __init__(self, taxonomy, slugify_mode, value, is_combination):
        super(HasTaxonomyTermsFilterClause, self).__init__(
                taxonomy.setting_name, value)
        self._taxonomy = taxonomy
        self._is_combination = is_combination
        self._slugifier = _Slugifier(taxonomy, slugify_mode)

    def pageMatches(self, fil, page):
        if self._taxonomy.is_multiple:
            # Multiple taxonomy, i.e. it supports multiple terms, like tags.
            page_values = fil.value_accessor(page, self.name)
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
        else:
            # Single taxonomy. Just compare the values.
            page_value = fil.value_accessor(page, self.name)
            if page_value is None:
                return False
            page_value = self._slugifier.slugify(page_value)
            return page_value == self.value


class _Slugifier(object):
    def __init__(self, taxonomy, mode):
        self.taxonomy = taxonomy
        self.mode = mode

    def slugify(self, term):
        if isinstance(term, tuple):
            return self.taxonomy.separator.join(
                    map(self._slugifyOne, term))
        return self._slugifyOne(term)

    def _slugifyOne(self, term):
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

