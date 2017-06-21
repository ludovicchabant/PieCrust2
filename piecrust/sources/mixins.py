import os.path
import logging
from piecrust import osutil
from piecrust.sources.base import ContentItem


logger = logging.getLogger(__name__)

assets_suffix = '-assets'


class SimpleAssetsSubDirMixin:
    """ A content source mixin for sources that are file-system-based,
        and have item assets stored in a sub-folder that is named after
        the item.

        More specifically, assets are stored in a sub-folder named:
        `<item_path>-assets`
    """
    def _getRelatedAssetsContents(self, item):
        spec_no_ext, _ = os.path.splitext(item.spec)
        assets_dir = spec_no_ext + assets_suffix
        try:
            asset_files = list(osutil.listdir(assets_dir))
        except (OSError, FileNotFoundError):
            return None

        assets = []
        for f in asset_files:
            fpath = os.path.join(assets_dir, f)
            name, _ = os.path.splitext(f)
            assets.append(ContentItem(
                fpath,
                {'name': name,
                 'filename': f,
                 '__is_asset': True}))
        return assets

    def _removeAssetGroups(self, groups):
        asset_groups = [g for g in groups
                        if g.spec.endswith(assets_suffix)]
        for g in asset_groups:
            groups.remove(g)
