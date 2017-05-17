import os.path
import queue
import logging
import threading
import urllib.parse
from piecrust.pipelines._pagerecords import SubPagePipelineRecordEntry
from piecrust.rendering import RenderingContext, render_page, PASS_FORMATTING
from piecrust.uriutil import split_uri


logger = logging.getLogger(__name__)


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
        self._writer_queue = None
        self._writer = None

    def startWriterQueue(self):
        self._writer_queue = queue.Queue()
        self._writer = threading.Thread(
            name='PageSerializer',
            target=_text_writer,
            args=(self._writer_queue,))
        self._writer.start()

    def stopWriterQueue(self):
        self._writer_queue.put_nowait(None)
        self._writer.join()

    def getOutputPath(self, uri, pretty_urls):
        uri_root, uri_path = split_uri(self.app, uri)

        bake_path = [self.out_dir]
        decoded_uri = urllib.parse.unquote(uri_path)
        if pretty_urls:
            bake_path.append(decoded_uri)
            bake_path.append('index.html')
        elif decoded_uri == '':
            bake_path.append('index.html')
        else:
            bake_path.append(decoded_uri)

        return os.path.normpath(os.path.join(*bake_path))

    def bake(self, qualified_page, prev_entry, dirty_source_names):
        # Start baking the sub-pages.
        cur_sub = 1
        has_more_subs = True
        sub_entries = []
        pretty_urls = qualified_page.config.get(
            'pretty_urls', self.pretty_urls)

        while has_more_subs:
            sub_page = qualified_page.getSubPage(cur_sub)
            sub_uri = sub_page.uri
            logger.debug("Baking '%s' [%d]..." % (sub_uri, cur_sub))

            out_path = self.getOutputPath(sub_uri, pretty_urls)

            # Create the sub-entry for the bake record.
            sub_entry = SubPagePipelineRecordEntry(sub_uri, out_path)
            sub_entries.append(sub_entry)

            # Find a corresponding sub-entry in the previous bake record.
            prev_sub_entry = None
            if prev_entry is not None:
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
                    in_path_time = qualified_page.path_mtime
                    out_path_time = os.path.getmtime(out_path)
                    if out_path_time >= in_path_time:
                        do_bake = False
                except OSError:
                    # File doesn't exist, we'll need to bake.
                    pass

            # If this page didn't bake because it's already up-to-date.
            # Keep trying for as many subs as we know this page has.
            if not do_bake:
                sub_entry.render_info = prev_sub_entry.copyRenderInfo()
                sub_entry.flags = SubPagePipelineRecordEntry.FLAG_NONE

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
                        SubPagePipelineRecordEntry.FLAG_FORMATTING_INVALIDATED

                logger.debug("  p%d -> %s" % (cur_sub, out_path))
                rp = self._bakeSingle(qualified_page, cur_sub, out_path)
            except Exception as ex:
                logger.exception(ex)
                page_rel_path = os.path.relpath(qualified_page.path,
                                                self.app.root_dir)
                raise BakingError("%s: error baking '%s'." %
                                  (page_rel_path, sub_uri)) from ex

            # Record what we did.
            sub_entry.flags |= SubPagePipelineRecordEntry.FLAG_BAKED
            sub_entry.render_info = rp.copyRenderInfo()

            # Copy page assets.
            if (cur_sub == 1 and self.copy_assets and
                    sub_entry.anyPass(lambda p: p.used_assets)):
                if pretty_urls:
                    out_assets_dir = os.path.dirname(out_path)
                else:
                    out_assets_dir, out_name = os.path.split(out_path)
                    if sub_uri != self.site_root:
                        out_name_noext, _ = os.path.splitext(out_name)
                        out_assets_dir = os.path.join(out_assets_dir,
                                                      out_name_noext)

                logger.debug("Copying page assets to: %s" % out_assets_dir)
                _ensure_dir_exists(out_assets_dir)

                qualified_page.source.buildAssetor(qualified_page, sub_uri).copyAssets(out_assets_dir)

            # Figure out if we have more work.
            has_more_subs = False
            if sub_entry.anyPass(lambda p: p.pagination_has_more):
                cur_sub += 1
                has_more_subs = True

        return sub_entries

    def _bakeSingle(self, qp, out_path):
        ctx = RenderingContext(qp)
        qp.source.prepareRenderContext(ctx)

        with self.app.env.timerScope("PageRender"):
            rp = render_page(ctx)

        with self.app.env.timerScope("PageSerialize"):
            if self._writer_queue is not None:
                self._writer_queue.put_nowait((out_path, rp.content))
            else:
                with open(out_path, 'w', encoding='utf8') as fp:
                    fp.write(rp.content)

        return rp


def _text_writer(q):
    while True:
        item = q.get()
        if item is not None:
            out_path, txt = item
            out_dir = os.path.dirname(out_path)
            _ensure_dir_exists(out_dir)

            with open(out_path, 'w', encoding='utf8') as fp:
                fp.write(txt)

            q.task_done()
        else:
            # Sentinel object, terminate the thread.
            q.task_done()
            break


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
                SubPagePipelineRecordEntry.FLAG_FORCED_BY_SOURCE
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
            SubPagePipelineRecordEntry.FLAG_FORCED_BY_PREVIOUS_ERRORS
        force_this_sub = True
    elif not prev_sub_entry:
        # No previous record. We'll have to bake it.
        logger.debug("No previous record entry found for '%s'. Will "
                     "force bake it." % sub_uri)
        sub_entry.flags |= \
            SubPagePipelineRecordEntry.FLAG_FORCED_BY_NO_PREVIOUS
        force_this_sub = True

    return force_this_sub, invalidate_formatting


def _get_dirty_source_names_and_render_passes(sub_entry, dirty_source_names):
    dirty_for_this = set()
    invalidated_render_passes = set()
    for p, pinfo in enumerate(sub_entry.render_info):
        if pinfo:
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

