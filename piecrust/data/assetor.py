import os
import os.path
import shutil
import logging
import collections.abc
from piecrust import ASSET_DIR_SUFFIX
from piecrust.sources.base import REL_ASSETS
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


class UnsupportedAssetsError(Exception):
    pass


class _AssetInfo:
    def __init__(self, content_item, uri):
        self.content_item = content_item
        self.uri = uri


class Assetor(collections.abc.Mapping):
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
            return self._cache[name].uri
        except KeyError:
            raise AttributeError()

    def __getitem__(self, key):
        self._cacheAssets()
        return self._cache[key].uri

    def __iter__(self):
        self._cacheAssets()
        return self._cache.keys()

    def __len__(self):
        self._cacheAssets()
        return len(self._cache)

    def _debugRenderAssetNames(self):
        self._cacheAssets()
        return list(self._cache.keys())

    def _cacheAssets(self):
        if self._cache is not None:
            return

        source = self._page.source
        content_item = self._page.content_item

        assets = source.getRelatedContents(content_item, REL_ASSETS)
        if assets is None:
            self._cache = {}
            return

        self._cache = {}

        app = source.app
        root_dir = app.root_dir
        asset_url_format = app.config.get('site/asset_url_format')

        page_uri = self._page.getUri()
        pretty_urls = app.config.get('site/pretty_urls')
        if not pretty_urls:
            page_uri, _ = os.path.splitext(page_uri)

        uri_build_tokens = {
            '%path%': None,
            '%filename%': None,
            '%page_uri%': page_uri
        }

        for a in assets:
            name = a.metadata['name']
            if name in self._cache:
                raise UnsupportedAssetsError(
                    "An asset with name '%s' already exists for item '%s'. "
                    "Do you have multiple assets with colliding names?" %
                    (name, content_item.spec))

            # TODO: this assumes a file-system source!
            uri_build_tokens['%path%'] = (
                os.path.relpath(a.spec, root_dir).replace('\\', '/'))
            uri_build_tokens['%filename%'] = a.metadata['filename'],
            uri = multi_replace(asset_url_format, uri_build_tokens)

            self._cache[name] = _AssetInfo(a, uri)

        stack = app.env.render_ctx_stack
        cur_ctx = stack.current_ctx
        if cur_ctx is not None:
            cur_ctx.current_pass_info.used_assets = True

    def copyAssets(self, dest_dir):
        page_pathname, _ = os.path.splitext(self._page.path)
        in_assets_dir = page_pathname + ASSET_DIR_SUFFIX
        for fn in os.listdir(in_assets_dir):
            full_fn = os.path.join(in_assets_dir, fn)
            if os.path.isfile(full_fn):
                dest_ap = os.path.join(dest_dir, fn)
                logger.debug("  %s -> %s" % (full_fn, dest_ap))
                shutil.copy(full_fn, dest_ap)

