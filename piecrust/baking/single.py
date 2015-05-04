import os.path
import copy
import shutil
import codecs
import logging
import urllib.parse
from piecrust.baking.records import (
        BakeRecordPassInfo, BakeRecordPageEntry, BakeRecordSubPageEntry)
from piecrust.data.filters import (
        PaginationFilter, HasFilterClause,
        IsFilterClause, AndBooleanClause,
        page_value_accessor)
from piecrust.rendering import (
        QualifiedPage, PageRenderingContext, render_page,
        PASS_FORMATTING, PASS_RENDERING)
from piecrust.sources.base import (
        PageFactory,
        REALM_NAMES, REALM_USER, REALM_THEME)
from piecrust.uriutil import split_uri


logger = logging.getLogger(__name__)


def copy_public_page_config(config):
    res = config.getDeepcopy()
    for k in list(res.keys()):
        if k.startswith('__'):
            del res[k]
    return res


class BakingError(Exception):
    pass


class PageBaker(object):
    def __init__(self, app, out_dir, force=False, record=None,
                 copy_assets=True):
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.record = record
        self.copy_assets = copy_assets
        self.site_root = app.config.get('site/root')
        self.pretty_urls = app.config.get('site/pretty_urls')

    def getOutputPath(self, uri):
        uri_root, uri_path = split_uri(self.app, uri)

        bake_path = [self.out_dir]
        decoded_uri = urllib.parse.unquote(uri_path)
        if self.pretty_urls:
            bake_path.append(decoded_uri)
            bake_path.append('index.html')
        elif decoded_uri == '':
            bake_path.append('index.html')
        else:
            bake_path.append(decoded_uri)

        return os.path.normpath(os.path.join(*bake_path))

    def bake(self, factory, route, record_entry):
        # Get the page.
        page = factory.buildPage()
        route_metadata = copy.deepcopy(factory.metadata)

        # Add taxonomy info in the template data and route metadata if needed.
        bake_taxonomy_info = None
        if record_entry.taxonomy_info:
            tax_name, tax_term, tax_source_name = record_entry.taxonomy_info
            taxonomy = self.app.getTaxonomy(tax_name)
            slugified_term = route.slugifyTaxonomyTerm(tax_term)
            route_metadata[taxonomy.term_name] = slugified_term
            bake_taxonomy_info = (taxonomy, tax_term)

        # Generate the URI.
        uri = route.getUri(route_metadata, provider=page)

        # See if this URL has been overriden by a previously baked page.
        # If that page is from another realm (e.g. a user page vs. a theme
        # page), we silently skip this page. If they're from the same realm,
        # we don't allow overriding and raise an error (this is probably
        # because of a misconfigured configuration that allows for ambiguous
        # URLs between 2 routes or sources).
        override = self.record.getOverrideEntry(factory, uri)
        if override is not None:
            override_source = self.app.getSource(override.source_name)
            if override_source.realm == factory.source.realm:
                raise BakingError(
                        "Page '%s' maps to URL '%s' but is overriden by page"
                        "'%s:%s'." % (factory.ref_spec, uri,
                                      override.source_name,
                                      override.rel_path))
            logger.debug("'%s' [%s] is overriden by '%s:%s'. Skipping" %
                         (factory.ref_spec, uri, override.source_name,
                          override.rel_path))
            record_entry.flags |= BakeRecordPageEntry.FLAG_OVERRIDEN
            return

        # Setup the record entry.
        record_entry.config = copy_public_page_config(page.config)

        # Start baking the sub-pages.
        cur_sub = 1
        has_more_subs = True
        force_this = self.force
        invalidate_formatting = False
        prev_record_entry = self.record.getPreviousEntry(
                factory.source.name, factory.rel_path,
                record_entry.taxonomy_info)

        logger.debug("Baking '%s'..." % uri)

        while has_more_subs:
            # Get the URL and path for this sub-page.
            sub_uri = route.getUri(route_metadata, sub_num=cur_sub,
                                   provider=page)
            out_path = self.getOutputPath(sub_uri)

            # Create the sub-entry for the bake record.
            record_sub_entry = BakeRecordSubPageEntry(sub_uri, out_path)
            record_entry.subs.append(record_sub_entry)

            # Find a corresponding sub-entry in the previous bake record.
            prev_record_sub_entry = None
            if prev_record_entry:
                try:
                    prev_record_sub_entry = prev_record_entry.getSub(cur_sub)
                except IndexError:
                    pass

            # Figure out what to do with this page.
            if (prev_record_sub_entry and
                    (prev_record_sub_entry.was_baked_successfully or
                        prev_record_sub_entry.was_clean)):
                # If the current page is known to use pages from other sources,
                # see if any of those got baked, or are going to be baked for
                # some reason. If so, we need to bake this one too.
                # (this happens for instance with the main page of a blog).
                dirty_src_names, invalidated_render_passes = (
                        self._getDirtySourceNamesAndRenderPasses(
                            prev_record_sub_entry))
                if len(invalidated_render_passes) > 0:
                    logger.debug(
                            "'%s' is known to use sources %s, which have "
                            "items that got (re)baked. Will force bake this "
                            "page. " % (uri, dirty_src_names))
                    record_sub_entry.flags |= \
                        BakeRecordSubPageEntry.FLAG_FORCED_BY_SOURCE
                    force_this = True

                    if PASS_FORMATTING in invalidated_render_passes:
                        logger.debug(
                                "Will invalidate cached formatting for '%s' "
                                "since sources were using during that pass."
                                % uri)
                        invalidate_formatting = True
            elif (prev_record_sub_entry and
                    prev_record_sub_entry.errors):
                # Previous bake failed. We'll have to bake it again.
                logger.debug(
                        "Previous record entry indicates baking failed for "
                        "'%s'. Will bake it again." % uri)
                record_sub_entry.flags |= \
                    BakeRecordSubPageEntry.FLAG_FORCED_BY_PREVIOUS_ERRORS
                force_this = True
            elif not prev_record_sub_entry:
                # No previous record. We'll have to bake it.
                logger.debug("No previous record entry found for '%s'. Will "
                             "force bake it." % uri)
                record_sub_entry.flags |= \
                    BakeRecordSubPageEntry.FLAG_FORCED_BY_NO_PREVIOUS
                force_this = True

            # Check for up-to-date outputs.
            do_bake = True
            if not force_this:
                try:
                    in_path_time = page.path_mtime
                    out_path_time = os.path.getmtime(out_path)
                    if out_path_time >= in_path_time:
                        do_bake = False
                except OSError:
                    # File doesn't exist, we'll need to bake.
                    pass

            # If this page didn't bake because it's already up-to-date.
            # Keep trying for as many subs as we know this page has.
            if not do_bake:
                prev_record_sub_entry.collapseRenderPasses(record_sub_entry)
                record_sub_entry.flags = BakeRecordSubPageEntry.FLAG_NONE

                if prev_record_entry.num_subs >= cur_sub + 1:
                    cur_sub += 1
                    has_more_subs = True
                    logger.debug("  %s is up to date, skipping to next "
                                 "sub-page." % out_path)
                    continue

                logger.debug("  %s is up to date, skipping bake." % out_path)
                break

            # All good, proceed.
            try:
                if invalidate_formatting:
                    cache_key = sub_uri
                    self.app.env.rendered_segments_repository.invalidate(
                            cache_key)
                    record_sub_entry.flags |= \
                        BakeRecordSubPageEntry.FLAG_FORMATTING_INVALIDATED

                logger.debug("  p%d -> %s" % (cur_sub, out_path))
                qp = QualifiedPage(page, route, route_metadata)
                ctx, rp = self._bakeSingle(qp, cur_sub, out_path,
                                           bake_taxonomy_info)
            except Exception as ex:
                if self.app.debug:
                    logger.exception(ex)
                page_rel_path = os.path.relpath(page.path, self.app.root_dir)
                raise BakingError("%s: error baking '%s'." %
                                  (page_rel_path, uri)) from ex

            # Record what we did.
            record_sub_entry.flags |= BakeRecordSubPageEntry.FLAG_BAKED
            self.record.dirty_source_names.add(record_entry.source_name)
            for p, pinfo in ctx.render_passes.items():
                brpi = BakeRecordPassInfo()
                brpi.used_source_names = set(pinfo.used_source_names)
                brpi.used_taxonomy_terms = set(pinfo.used_taxonomy_terms)
                record_sub_entry.render_passes[p] = brpi
            if prev_record_sub_entry:
                prev_record_sub_entry.collapseRenderPasses(record_sub_entry)

            # Copy page assets.
            if (cur_sub == 1 and self.copy_assets and
                    ctx.used_assets is not None):
                if self.pretty_urls:
                    out_assets_dir = os.path.dirname(out_path)
                else:
                    out_assets_dir, out_name = os.path.split(out_path)
                    if sub_uri != self.site_root:
                        out_name_noext, _ = os.path.splitext(out_name)
                        out_assets_dir += out_name_noext

                logger.debug("Copying page assets to: %s" % out_assets_dir)
                if not os.path.isdir(out_assets_dir):
                    os.makedirs(out_assets_dir, 0o755)
                for ap in ctx.used_assets:
                    dest_ap = os.path.join(out_assets_dir,
                                           os.path.basename(ap))
                    logger.debug("  %s -> %s" % (ap, dest_ap))
                    shutil.copy(ap, dest_ap)
                    record_entry.assets.append(ap)

            # Figure out if we have more work.
            has_more_subs = False
            if ctx.used_pagination is not None:
                if ctx.used_pagination.has_more:
                    cur_sub += 1
                    has_more_subs = True

    def _bakeSingle(self, qualified_page, num, out_path, taxonomy_info=None):
        ctx = PageRenderingContext(qualified_page, page_num=num)
        if taxonomy_info:
            ctx.setTaxonomyFilter(taxonomy_info[0], taxonomy_info[1])

        rp = render_page(ctx)

        out_dir = os.path.dirname(out_path)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, 0o755)

        with codecs.open(out_path, 'w', 'utf8') as fp:
            fp.write(rp.content)

        return ctx, rp

    def _getDirtySourceNamesAndRenderPasses(self, record_sub_entry):
        dirty_src_names = set()
        invalidated_render_passes = set()
        for p, pinfo in record_sub_entry.render_passes.items():
            for src_name in pinfo.used_source_names:
                is_dirty = (src_name in self.record.dirty_source_names)
                if is_dirty:
                    invalidated_render_passes.add(p)
                    dirty_src_names.add(src_name)
                    break
        return dirty_src_names, invalidated_render_passes

