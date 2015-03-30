import os.path
import shutil
import codecs
import logging
import urllib.parse
from piecrust.baking.records import FLAG_OVERRIDEN, FLAG_SOURCE_MODIFIED
from piecrust.data.filters import (PaginationFilter, HasFilterClause,
        IsFilterClause, AndBooleanClause,
        page_value_accessor)
from piecrust.rendering import (PageRenderingContext, render_page,
        PASS_FORMATTING, PASS_RENDERING)
from piecrust.sources.base import (PageFactory,
        REALM_NAMES, REALM_USER, REALM_THEME)


logger = logging.getLogger(__name__)


def copy_public_page_config(config):
    res = config.get().copy()
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
        self.pagination_suffix = app.config.get('site/pagination_suffix')

    def getOutputPath(self, uri):
        bake_path = [self.out_dir]
        decoded_uri = urllib.parse.unquote(uri.lstrip('/'))
        if self.pretty_urls:
            bake_path.append(decoded_uri)
            bake_path.append('index.html')
        elif decoded_uri == '':
            bake_path.append('index.html')
        else:
            bake_path.append(decoded_uri)

        return os.path.normpath(os.path.join(*bake_path))

    def bake(self, factory, route, record_entry,
             taxonomy_name=None, taxonomy_term=None):
        taxonomy = None
        route_metadata = dict(factory.metadata)
        if taxonomy_name and taxonomy_term:
            # TODO: add options for combining and slugifying terms
            taxonomy = self.app.getTaxonomy(taxonomy_name)
            if taxonomy.is_multiple:
                if isinstance(taxonomy_term, tuple):
                    slugified_term = '/'.join(taxonomy_term)
                else:
                    slugified_term = taxonomy_term
            else:
                slugified_term = taxonomy_term
            route_metadata.update({taxonomy.setting_name: slugified_term})

        # Generate the URL using the route.
        page = factory.buildPage()
        uri = route.getUri(route_metadata, provider=page,
                           include_site_root=False)

        override = self.record.getOverrideEntry(factory, uri)
        if override is not None:
            override_source = self.app.getSource(override.source_name)
            if override_source.realm == factory.source.realm:
                raise BakingError(
                        "Page '%s' maps to URL '%s' but is overriden by page"
                        "'%s:%s'." % (factory.ref_spec, uri,
                            override.source_name, override.rel_path))
            logger.debug("'%s' [%s] is overriden by '%s:%s'. Skipping" %
                    (factory.ref_spec, uri, override.source_name,
                        override.rel_path))
            record_entry.flags |= FLAG_OVERRIDEN
            return

        cur_sub = 1
        has_more_subs = True
        force_this = self.force
        invalidate_formatting = False
        record_entry.config = copy_public_page_config(page.config)
        prev_record_entry = self.record.getPreviousEntry(
                factory.source.name, factory.rel_path,
                taxonomy_name, taxonomy_term)

        logger.debug("Baking '%s'..." % uri)

        # If the current page is known to use pages from other sources,
        # see if any of those got baked, or are going to be baked for some
        # reason. If so, we need to bake this one too.
        # (this happens for instance with the main page of a blog).
        if prev_record_entry and prev_record_entry.was_baked_successfully:
            invalidated_render_passes = set()
            used_src_names = list(prev_record_entry.used_source_names)
            for src_name, rdr_pass in used_src_names:
                entries = self.record.getCurrentEntries(src_name)
                for e in entries:
                    if e.was_baked or e.flags & FLAG_SOURCE_MODIFIED:
                        invalidated_render_passes.add(rdr_pass)
                        break
            if len(invalidated_render_passes) > 0:
                logger.debug("'%s' is known to use sources %s, at least one "
                             "of which got baked. Will force bake this page. "
                             % (uri, used_src_names))
                force_this = True
                if PASS_FORMATTING in invalidated_render_passes:
                    logger.debug("Will invalidate cached formatting for '%s' "
                                 "since sources were using during that pass."
                                 % uri)
                    invalidate_formatting = True

        while has_more_subs:
            sub_uri = route.getUri(route_metadata, sub_num=cur_sub,
                                   provider=page, include_site_root=False)
            out_path = self.getOutputPath(sub_uri)

            # Check for up-to-date outputs.
            do_bake = True
            if not force_this:
                try:
                    in_path_time = record_entry.path_mtime
                    out_path_time = os.path.getmtime(out_path)
                    if out_path_time >= in_path_time:
                        do_bake = False
                except OSError:
                    # File doesn't exist, we'll need to bake.
                    pass

            # If this page didn't bake because it's already up-to-date.
            # Keep trying for as many subs as we know this page has.
            if not do_bake:
                if (prev_record_entry is not None and
                        prev_record_entry.num_subs < cur_sub):
                    logger.debug("")
                    cur_sub += 1
                    has_more_subs = True
                    logger.debug("  %s is up to date, skipping to next "
                            "sub-page." % out_path)
                    continue

                # We don't know how many subs to expect... just skip.
                logger.debug("  %s is up to date, skipping bake." % out_path)
                break

            # All good, proceed.
            try:
                if invalidate_formatting:
                    cache_key = '%s:%s' % (uri, cur_sub)
                    self.app.env.rendered_segments_repository.invalidate(
                            cache_key)

                logger.debug("  p%d -> %s" % (cur_sub, out_path))
                ctx, rp = self._bakeSingle(page, sub_uri, cur_sub, out_path,
                                           taxonomy, taxonomy_term)
            except Exception as ex:
                if self.app.debug:
                    logger.exception(ex)
                page_rel_path = os.path.relpath(page.path, self.app.root_dir)
                raise BakingError("%s: error baking '%s'." %
                        (page_rel_path, uri)) from ex

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
                    dest_ap = os.path.join(out_assets_dir, os.path.basename(ap))
                    logger.debug("  %s -> %s" % (ap, dest_ap))
                    shutil.copy(ap, dest_ap)

            # Record what we did and figure out if we have more work.
            record_entry.out_uris.append(sub_uri)
            record_entry.out_paths.append(out_path)
            record_entry.used_source_names |= ctx.used_source_names
            record_entry.used_taxonomy_terms |= ctx.used_taxonomy_terms

            has_more_subs = False
            if (ctx.used_pagination is not None and
                    ctx.used_pagination.has_more):
                cur_sub += 1
                has_more_subs = True

    def _bakeSingle(self, page, sub_uri, num, out_path,
                    taxonomy=None, taxonomy_term=None):
        ctx = PageRenderingContext(page, sub_uri)
        ctx.page_num = num
        if taxonomy and taxonomy_term:
            ctx.setTaxonomyFilter(taxonomy, taxonomy_term)

        rp = render_page(ctx)

        out_dir = os.path.dirname(out_path)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, 0o755)

        with codecs.open(out_path, 'w', 'utf8') as fp:
            fp.write(rp.content)

        return ctx, rp

