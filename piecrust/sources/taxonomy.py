import re
import time
import logging
import unidecode
from piecrust.chefutil import format_timed, format_timed_scope
from piecrust.configuration import ConfigurationError
from piecrust.data.filters import (
    PaginationFilter, SettingFilterClause,
    page_value_accessor)
from piecrust.routing import RouteParameter
from piecrust.sources.base import ContentSource, GeneratedContentException


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

    @property
    def setting_name(self):
        if self.is_multiple:
            return self.name
        return self.term_name


class TaxonomySource(ContentSource):
    """ A page generator that handles taxonomies, _i.e._ lists of keywords
        that pages are labelled with, and for which we need to generate
        listing pages.
    """
    SOURCE_NAME = 'taxonomy'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)

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
        self.slugifier = _Slugifier(self.taxonomy, self.slugify_mode)

    def getContents(self, group):
        raise GeneratedContentException()

    def getSupportedRouteParameters(self):
        name = self.taxonomy.term_name
        param_type = (RouteParameter.TYPE_PATH if self.taxonomy.is_multiple
                      else RouteParameter.TYPE_STRING)
        return [RouteParameter(name, param_type,
                               variadic=self.taxonomy.is_multiple)]

    def slugify(self, term):
        return self.slugifier.slugify(term)

    def slugifyMultiple(self, terms):
        return self.slugifier.slugifyMultiple(terms)

    def prepareRenderContext(self, ctx):
        # Set the pagination source as the source we're generating for.
        ctx.pagination_source = self.source

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
        tax_terms, is_combination = self._getTaxonomyTerms(
                ctx.page.route_metadata)
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

    def _getSource(self):
        return self.app.getSource(self.config['source'])

    def _getTaxonomyTerms(self, route_metadata):
        # Get the individual slugified terms from the route metadata.
        all_values = route_metadata.get(self.taxonomy.term_name)
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
        flt = PaginationFilter(value_accessor=page_value_accessor)
        flt.addClause(HasTaxonomyTermsFilterClause(
                self.taxonomy, self.slugify_mode, term_value, is_combination))
        ctx.pagination_filter = flt

    def onRouteFunctionUsed(self, route, route_metadata):
        # Get the values, and slugify them appropriately.
        values = route_metadata[self.taxonomy.term_name]
        if self.taxonomy.is_multiple:
            # TODO: here we assume the route has been properly configured.
            slugified_values = self.slugifyMultiple((str(v) for v in values))
            route_val = self.taxonomy.separator.join(slugified_values)
        else:
            slugified_values = self.slugify(str(values))
            route_val = slugified_values

        # We need to register this use of a taxonomy term.
        eis = self.app.env.exec_info_stack
        cpi = eis.current_page_info.render_ctx.current_pass_info
        if cpi:
            utt = cpi.getCustomInfo('used_taxonomy_terms', [], True)
            utt.append(slugified_values)

        # Put the slugified values in the route metadata so they're used to
        # generate the URL.
        route_metadata[self.taxonomy.term_name] = route_val

    def bake(self, ctx):
        if not self.page_ref.exists:
            logger.debug(
                    "No page found at '%s', skipping taxonomy '%s'." %
                    (self.page_ref, self.taxonomy.name))
            return

        logger.debug("Baking %s pages...", self.taxonomy.name)
        analyzer = _TaxonomyTermsAnalyzer(self.source_name, self.taxonomy,
                                          self.slugify_mode)
        with format_timed_scope(logger, 'gathered taxonomy terms',
                                level=logging.DEBUG, colored=False):
            analyzer.analyze(ctx)

        start_time = time.perf_counter()
        page_count = self._bakeTaxonomyTerms(ctx, analyzer)
        if page_count > 0:
            logger.info(format_timed(
                start_time,
                "baked %d %s pages for %s." % (
                    page_count, self.taxonomy.term_name, self.source_name)))

    def _bakeTaxonomyTerms(self, ctx, analyzer):
        # Start baking those terms.
        logger.debug(
                "Baking '%s' for source '%s': %d terms" %
                (self.taxonomy.name, self.source_name,
                 len(analyzer.dirty_slugified_terms)))

        route = self.app.getGeneratorRoute(self.name)
        if route is None:
            raise Exception("No routes have been defined for generator: %s" %
                            self.name)

        logger.debug("Using taxonomy page: %s" % self.page_ref)
        fac = self.page_ref.getFactory()

        job_count = 0
        for slugified_term in analyzer.dirty_slugified_terms:
            extra_route_metadata = {
                self.taxonomy.term_name: slugified_term}

            # Use the slugified term as the record's extra key seed.
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

                if analyzer.isKnownSlugifiedTerm(t):
                    logger.debug("Creating unbaked entry for %s term: %s" %
                                 (self.name, t))
                    ctx.collapseRecord(prev_entry)
                else:
                    logger.debug("Term %s in %s isn't used anymore." %
                                 (self.name, t))

        return job_count


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


class _TaxonomyTermsAnalyzer(object):
    def __init__(self, source_name, taxonomy, slugify_mode):
        self.source_name = source_name
        self.taxonomy = taxonomy
        self.slugifier = _Slugifier(taxonomy, slugify_mode)
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

    def analyze(self, ctx):
        # Build the list of terms for our taxonomy, and figure out which ones
        # are 'dirty' for the current bake.
        #
        # Remember all terms used.
        for _, cur_entry in ctx.getAllPageRecords():
            if cur_entry and not cur_entry.was_overriden:
                cur_terms = cur_entry.config.get(self.taxonomy.setting_name)
                if cur_terms:
                    if not self.taxonomy.is_multiple:
                        self._addTerm(cur_entry.path, cur_terms)
                    else:
                        self._addTerms(cur_entry.path, cur_terms)

        # Re-bake all taxonomy terms that include new or changed pages, by
        # marking them as 'dirty'.
        for prev_entry, cur_entry in ctx.getBakedPageRecords():
            if cur_entry.source_name != self.source_name:
                continue

            entries = [cur_entry]
            if prev_entry:
                entries.append(prev_entry)

            for e in entries:
                entry_terms = e.config.get(self.taxonomy.setting_name)
                if entry_terms:
                    if not self.taxonomy.is_multiple:
                        self._single_dirty_slugified_terms.add(
                            self.slugifier.slugify(entry_terms))
                    else:
                        self._single_dirty_slugified_terms.update(
                            (self.slugifier.slugify(t)
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
        if self.taxonomy.is_multiple:
            known_combinations = set()
            for _, cur_entry in ctx.getAllPageRecords():
                if cur_entry:
                    used_terms = _get_all_entry_taxonomy_terms(cur_entry)
                    for terms in used_terms:
                        if len(terms) > 1:
                            known_combinations.add(terms)

            dcc = 0
            for terms in known_combinations:
                if not self._single_dirty_slugified_terms.isdisjoint(
                        set(terms)):
                    self._all_dirty_slugified_terms.append(
                        self.taxonomy.separator.join(terms))
                    dcc += 1
            logger.debug("Gathered %d term combinations, with %d dirty." %
                         (len(known_combinations), dcc))

    def _addTerms(self, entry_path, terms):
        for t in terms:
            self._addTerm(entry_path, t)

    def _addTerm(self, entry_path, term):
        st = self.slugifier.slugify(term)
        orig_terms = self._all_terms.setdefault(st, [])
        if orig_terms and orig_terms[0] != term:
            logger.warning(
                "Term '%s' in '%s' is slugified to '%s' which conflicts with "
                "previously existing '%s'. The two will be merged." %
                (term, entry_path, st, orig_terms[0]))
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

