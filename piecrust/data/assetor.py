import os
import os.path
import shutil
import logging
from piecrust import ASSET_DIR_SUFFIX
from piecrust.sources.base import REL_ASSETS
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


class UnsupportedAssetsError(Exception):
    pass


def build_base_url(app, uri, rel_assets_path):
    base_url_format = app.config.get('site/base_asset_url_format')
    rel_assets_path = rel_assets_path.replace('\\', '/')

    # Remove any extension since we'll be copying assets into the 1st
    # sub-page's folder.
    pretty = app.config.get('site/pretty_urls')
    if not pretty:
        uri, _ = os.path.splitext(uri)

    base_url = multi_replace(
        base_url_format,
        {
            '%path%': rel_assets_path,
            '%uri%': uri})

    return base_url.rstrip('/') + '/'


class Assetor:
    debug_render_doc = """Helps render URLs to files in the current page's
                          asset folder."""
    debug_render = []
    debug_render_dynamic = ['_debugRenderAssetNames']

    def __init__(self, page):
        self._page = page
        self._cache = None

    def __getattr__(self, name):
        try:
            self._cacheAssets()
            return self._cache[name][0]
        except KeyError:
            raise AttributeError()

    def __getitem__(self, key):
        self._cacheAssets()
        return self._cache[key][0]

    def __iter__(self):
        self._cacheAssets()
        return map(lambda i: i[0], self._cache.values())

    def allNames(self):
        self._cacheAssets()
        return list(self._cache.keys())

    def _debugRenderAssetNames(self):
        self._cacheAssets()
        return list(self._cache.keys())

    def _cacheAssets(self):
        if self._cache is not None:
            return

        self._cache = self.findAssets() or {}

    def findAssets(self):
        content_item = self._page.content_item
        source = content_item.source
        assets = source.getRelatedContent(content_item, REL_ASSETS)
        if assets is None:
            return {}

        app = source.app
        stack = app.env.render_ctx_stack
        cur_ctx = stack.current_ctx
        if cur_ctx is not None:
            cur_ctx.current_pass_info.used_assets = True

        # base_url = build_base_url(app, self._uri, rel_assets_dir)

        return assets

    def copyAssets(self, dest_dir):
        page_pathname, _ = os.path.splitext(self._page.path)
        in_assets_dir = page_pathname + ASSET_DIR_SUFFIX
        for fn in os.listdir(in_assets_dir):
            full_fn = os.path.join(in_assets_dir, fn)
            if os.path.isfile(full_fn):
                dest_ap = os.path.join(dest_dir, fn)
                logger.debug("  %s -> %s" % (full_fn, dest_ap))
                shutil.copy(full_fn, dest_ap)

