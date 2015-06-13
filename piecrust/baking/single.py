import os.path
import shutil
import codecs
import logging
import urllib.parse
from piecrust.baking.records import (
        PageBakeInfo, SubPageBakeInfo, BakePassInfo)
from piecrust.rendering import (
        QualifiedPage, PageRenderingContext, render_page,
        PASS_FORMATTING)
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
    def __init__(self, app, out_dir, force=False, copy_assets=True):
        self.app = app
        self.out_dir = out_dir
        self.force = force
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

    def bake(self, factory, route, route_metadata, prev_entry,
             first_render_info, dirty_source_names, tax_info=None):
        # Get the page.
        page = factory.buildPage()

        # Start baking the sub-pages.
        cur_sub = 1
        has_more_subs = True
        report = PageBakeInfo()

        while has_more_subs:
            # Get the URL and path for this sub-page.
            sub_uri = route.getUri(route_metadata, sub_num=cur_sub,
                                   provider=page)
            logger.debug("Baking '%s' [%d]..." % (sub_uri, cur_sub))
            out_path = self.getOutputPath(sub_uri)

            # Create the sub-entry for the bake record.
            sub_entry = SubPageBakeInfo(sub_uri, out_path)
            report.subs.append(sub_entry)

            # Find a corresponding sub-entry in the previous bake record.
            prev_sub_entry = None
            if prev_entry:
                try:
                    prev_sub_entry = prev_entry.getSub(cur_sub)
                except IndexError:
                    pass

            # Figure out if we need to invalidate or force anything.
            force_this_sub, invalidate_formatting = _compute_force_flags(
                    prev_sub_entry, sub_entry, dirty_source_names)
            force_this_sub = force_this_sub or self.force

            # Check for up-to-date outputs.
            do_bake = True
            if not force_this_sub:
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
                prev_sub_entry.collapseRenderPasses(sub_entry)
                sub_entry.flags = SubPageBakeInfo.FLAG_NONE

                if prev_entry.num_subs >= cur_sub + 1:
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
                    sub_entry.flags |= \
                        SubPageBakeInfo.FLAG_FORMATTING_INVALIDATED

                logger.debug("  p%d -> %s" % (cur_sub, out_path))
                qp = QualifiedPage(page, route, route_metadata)
                ctx, rp = self._bakeSingle(qp, cur_sub, out_path, tax_info)
            except Exception as ex:
                if self.app.debug:
                    logger.exception(ex)
                page_rel_path = os.path.relpath(page.path, self.app.root_dir)
                raise BakingError("%s: error baking '%s'." %
                                  (page_rel_path, sub_uri)) from ex

            # Record what we did.
            sub_entry.flags |= SubPageBakeInfo.FLAG_BAKED
            # self.record.dirty_source_names.add(record_entry.source_name)
            for p, pinfo in ctx.render_passes.items():
                bpi = BakePassInfo()
                bpi.used_source_names = set(pinfo.used_source_names)
                bpi.used_taxonomy_terms = set(pinfo.used_taxonomy_terms)
                sub_entry.render_passes[p] = bpi
            if prev_sub_entry:
                prev_sub_entry.collapseRenderPasses(sub_entry)

            # If this page has had its first sub-page rendered already, we
            # have that information from the baker. Otherwise (e.g. for
            # taxonomy pages), we have that information from the result
            # of the render.
            info = ctx
            if cur_sub == 1 and first_render_info is not None:
                info = first_render_info

            # Copy page assets.
            if cur_sub == 1 and self.copy_assets and info.used_assets:
                if self.pretty_urls:
                    out_assets_dir = os.path.dirname(out_path)
                else:
                    out_assets_dir, out_name = os.path.split(out_path)
                    if sub_uri != self.site_root:
                        out_name_noext, _ = os.path.splitext(out_name)
                        out_assets_dir += out_name_noext

                logger.debug("Copying page assets to: %s" % out_assets_dir)
                _ensure_dir_exists(out_assets_dir)

                used_assets = info.used_assets
                for ap in used_assets:
                    dest_ap = os.path.join(out_assets_dir,
                                           os.path.basename(ap))
                    logger.debug("  %s -> %s" % (ap, dest_ap))
                    shutil.copy(ap, dest_ap)
                    report.assets.append(ap)

            # Figure out if we have more work.
            has_more_subs = False
            if info.pagination_has_more:
                cur_sub += 1
                has_more_subs = True

        return report

    def _bakeSingle(self, qualified_page, num, out_path, tax_info=None):
        ctx = PageRenderingContext(qualified_page, page_num=num)
        if tax_info:
            tax = self.app.getTaxonomy(tax_info.taxonomy_name)
            ctx.setTaxonomyFilter(tax, tax_info.term)

        rp = render_page(ctx)

        out_dir = os.path.dirname(out_path)
        _ensure_dir_exists(out_dir)

        with codecs.open(out_path, 'w', 'utf8') as fp:
            fp.write(rp.content)

        return ctx, rp


def _compute_force_flags(prev_sub_entry, sub_entry, dirty_source_names):
    # Figure out what to do with this page.
    force_this_sub = False
    invalidate_formatting = False
    sub_uri = sub_entry.out_uri
    if (prev_sub_entry and
            (prev_sub_entry.was_baked_successfully or
                prev_sub_entry.was_clean)):
        # If the current page is known to use pages from other sources,
        # see if any of those got baked, or are going to be baked for
        # some reason. If so, we need to bake this one too.
        # (this happens for instance with the main page of a blog).
        dirty_for_this, invalidated_render_passes = (
                _get_dirty_source_names_and_render_passes(
                    prev_sub_entry, dirty_source_names))
        if len(invalidated_render_passes) > 0:
            logger.debug(
                    "'%s' is known to use sources %s, which have "
                    "items that got (re)baked. Will force bake this "
                    "page. " % (sub_uri, dirty_for_this))
            sub_entry.flags |= \
                SubPageBakeInfo.FLAG_FORCED_BY_SOURCE
            force_this_sub = True

            if PASS_FORMATTING in invalidated_render_passes:
                logger.debug(
                        "Will invalidate cached formatting for '%s' "
                        "since sources were using during that pass."
                        % sub_uri)
                invalidate_formatting = True
    elif (prev_sub_entry and
            prev_sub_entry.errors):
        # Previous bake failed. We'll have to bake it again.
        logger.debug(
                "Previous record entry indicates baking failed for "
                "'%s'. Will bake it again." % sub_uri)
        sub_entry.flags |= \
            SubPageBakeInfo.FLAG_FORCED_BY_PREVIOUS_ERRORS
        force_this_sub = True
    elif not prev_sub_entry:
        # No previous record. We'll have to bake it.
        logger.debug("No previous record entry found for '%s'. Will "
                     "force bake it." % sub_uri)
        sub_entry.flags |= \
            SubPageBakeInfo.FLAG_FORCED_BY_NO_PREVIOUS
        force_this_sub = True

    return force_this_sub, invalidate_formatting


def _get_dirty_source_names_and_render_passes(
        sub_entry, dirty_source_names):
    dirty_for_this = set()
    invalidated_render_passes = set()
    for p, pinfo in sub_entry.render_passes.items():
        for src_name in pinfo.used_source_names:
            is_dirty = (src_name in dirty_source_names)
            if is_dirty:
                invalidated_render_passes.add(p)
                dirty_for_this.add(src_name)
                break
    return dirty_for_this, invalidated_render_passes


def _ensure_dir_exists(path):
    try:
        os.makedirs(path, mode=0o755, exist_ok=True)
    except OSError:
        # In a multiprocess environment, several process may very
        # occasionally try to create the same directory at the same time.
        # Let's ignore any error and if something's really wrong (like file
        # acces permissions or whatever), then it will more legitimately fail
        # just after this when we try to write files.
        pass

