import os.path
import copy
import queue
import shutil
import logging
import threading
import urllib.parse
from piecrust.pipelines._pagerecords import (
    SubPageFlags, create_subpage_job_result)
from piecrust.rendering import RenderingContext, render_page
from piecrust.sources.base import AbortedSourceUseError
from piecrust.uriutil import split_uri


logger = logging.getLogger(__name__)


def get_output_path(app, out_dir, uri, pretty_urls):
    uri_root, uri_path = split_uri(app, uri)

    bake_path = [out_dir]
    decoded_uri = urllib.parse.unquote(uri_path)
    if pretty_urls:
        bake_path.append(decoded_uri)
        bake_path.append('index.html')
    elif decoded_uri == '':
        bake_path.append('index.html')
    else:
        bake_path.append(decoded_uri)

    return os.path.normpath(os.path.join(*bake_path))


class BakingError(Exception):
    pass


class PageBaker(object):
    def __init__(self, app, out_dir, force=False):
        self.app = app
        self.out_dir = out_dir
        self.force = force
        self.site_root = app.config.get('site/root')
        self.pretty_urls = app.config.get('site/pretty_urls')
        self._do_write = self._writeDirect
        self._writer_queue = None
        self._writer = None
        self._stats = app.env.stats
        self._rsr = app.env.rendered_segments_repository

    def startWriterQueue(self):
        self._writer_queue = queue.Queue()
        self._writer = threading.Thread(
            name='PageSerializer',
            daemon=True,
            target=_text_writer,
            args=(self._writer_queue,))
        self._writer.start()
        self._do_write = self._sendToWriterQueue

    def stopWriterQueue(self):
        self._writer_queue.put_nowait(None)
        self._writer.join()

    def _sendToWriterQueue(self, out_path, content):
        self._writer_queue.put_nowait((out_path, content))

    def _writeDirect(self, out_path, content):
        with open(out_path, 'w', encoding='utf8') as fp:
            fp.write(content)

    def bake(self, page, prev_entry,
             force_segments=False, force_layout=False):
        cur_sub = 1
        has_more_subs = True
        app = self.app
        out_dir = self.out_dir
        force_segments = self.force or force_segments
        force_layout = self.force or force_layout
        pretty_urls = page.config.get('pretty_urls', self.pretty_urls)

        rendered_subs = []

        # Start baking the sub-pages.
        while has_more_subs:
            sub_uri = page.getUri(sub_num=cur_sub)
            logger.debug("Baking '%s' [%d]..." % (sub_uri, cur_sub))

            out_path = get_output_path(app, out_dir, sub_uri, pretty_urls)

            # Create the sub-entry for the bake record.
            cur_sub_entry = create_subpage_job_result(sub_uri, out_path)
            rendered_subs.append(cur_sub_entry)

            # Find a corresponding sub-entry in the previous bake record.
            prev_sub_entry = None
            if prev_entry is not None:
                try:
                    prev_sub_entry = prev_entry.getSub(cur_sub)
                except IndexError:
                    pass

            # Figure out if we need to bake this page.
            bake_status = _get_bake_status(page, out_path,
                                           force_segments, force_layout,
                                           prev_sub_entry, cur_sub_entry)

            # If this page didn't bake because it's already up-to-date.
            # Keep trying for as many subs as we know this page has.
            if bake_status == STATUS_CLEAN:
                cur_sub_entry['render_info'] = copy.deepcopy(
                    prev_sub_entry['render_info'])
                cur_sub_entry['flags'] = \
                    SubPageFlags.FLAG_COLLAPSED_FROM_LAST_RUN

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
                if bake_status == STATUS_INVALIDATE_AND_BAKE:
                    cache_key = sub_uri
                    self._rsr.invalidate(cache_key)
                    cur_sub_entry['flags'] |= \
                        SubPageFlags.FLAG_RENDER_CACHE_INVALIDATED

                logger.debug("  p%d -> %s" % (cur_sub, out_path))
                rp = self._bakeSingle(page, cur_sub, out_path)
            except AbortedSourceUseError:
                raise
            except Exception as ex:
                logger.exception(ex)
                raise BakingError("%s: error baking '%s'." %
                                  (page.content_spec, sub_uri)) from ex

            # Record what we did.
            cur_sub_entry['flags'] |= SubPageFlags.FLAG_BAKED
            cur_sub_entry['render_info'] = copy.deepcopy(rp.render_info)

            # Copy page assets.
            if (cur_sub == 1 and
                    cur_sub_entry['render_info']['used_assets']):
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
                assetor = rp.data.get('assets')
                if assetor is not None:
                    for i in assetor._getAssetItems():
                        fn = os.path.basename(i.spec)
                        out_asset_path = os.path.join(out_assets_dir, fn)
                        logger.debug("  %s -> %s" % (i.spec, out_asset_path))
                        shutil.copy(i.spec, out_asset_path)

            # Figure out if we have more work.
            has_more_subs = False
            if cur_sub_entry['render_info']['pagination_has_more']:
                cur_sub += 1
                has_more_subs = True

        return rendered_subs

    def _bakeSingle(self, page, sub_num, out_path):
        ctx = RenderingContext(page, sub_num=sub_num)
        page.source.prepareRenderContext(ctx)

        with self._stats.timerScope("PageRender"):
            rp = render_page(ctx)

        with self._stats.timerScope("PageSerialize"):
            self._do_write(out_path, rp.content)

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


STATUS_CLEAN = 0
STATUS_BAKE = 1
STATUS_INVALIDATE_AND_BAKE = 2


def _get_bake_status(page, out_path, force_segments, force_layout,
                     prev_sub_entry, cur_sub_entry):
    # Easy tests.
    if force_segments:
        return STATUS_INVALIDATE_AND_BAKE
    if force_layout:
        return STATUS_BAKE

    # Figure out if we need to invalidate or force anything.
    status = _compute_force_flags(prev_sub_entry, cur_sub_entry)
    if status != STATUS_CLEAN:
        return status

    # Check for up-to-date outputs.
    in_path_time = page.content_mtime
    try:
        out_path_time = os.path.getmtime(out_path)
    except OSError:
        # File doesn't exist, we'll need to bake.
        cur_sub_entry['flags'] |= \
            SubPageFlags.FLAG_FORCED_BY_NO_PREVIOUS
        return STATUS_BAKE

    if out_path_time <= in_path_time:
        return STATUS_BAKE

    # Nope, all good.
    return STATUS_CLEAN


def _compute_force_flags(prev_sub_entry, cur_sub_entry):
    if prev_sub_entry and len(prev_sub_entry['errors']) > 0:
        # Previous bake failed. We'll have to bake it again.
        cur_sub_entry['flags'] |= \
            SubPageFlags.FLAG_FORCED_BY_PREVIOUS_ERRORS
        return STATUS_BAKE

    if not prev_sub_entry:
        # No previous record, so most probably was never baked. Bake it.
        cur_sub_entry['flags'] |= \
            SubPageFlags.FLAG_FORCED_BY_NO_RECORD
        return STATUS_BAKE

    return STATUS_CLEAN


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

