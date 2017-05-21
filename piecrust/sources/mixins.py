import os.path
import logging
from piecrust import osutil
from piecrust.sources.base import ContentItem


logger = logging.getLogger(__name__)

assets_suffix = '-assets'


class SimpleAssetsSubDirMixin:
    def _getRelatedAssetsContents(self, item, relationship):
        if not item.metadata.get('__has_assets', False):
            return None

        assets = {}
        assets_dir = item.spec + assets_suffix
        for f in osutil.listdir(assets_dir):
            fpath = os.path.join(assets_dir, f)
            name, _ = os.path.splitext(f)
            if name in assets:
                raise Exception("Multiple assets are named '%s'." %
                                name)
            assets[name] = ContentItem(fpath, {'__is_asset': True})
        return assets

    def _onFinalizeContent(self, parent_group, items, groups):
        assetsGroups = []
        for g in groups:
            if not g.spec.endswith(assets_suffix):
                continue
            match = g.spec[:-len(assets_suffix)]
            item = next(filter(lambda i: i.spec == match), None)
            if item:
                item.metadata['__has_assets'] = True
                assetsGroups.append(g)
        for g in assetsGroups:
            groups.remove(g)

