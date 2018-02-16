import re
import os
import os.path
import logging
from piecrust.configuration import ConfigurationError
from piecrust.sources.base import ContentItem
from piecrust.sources.default import DefaultContentSource


logger = logging.getLogger(__name__)


class AutoConfigContentSourceBase(DefaultContentSource):
    """ Base class for content sources that automatically apply configuration
        settings to their generated pages based on those pages' paths.
    """
    def __init__(self, app, name, config):
        super().__init__(app, name, config)

        config.setdefault('data_type', 'page_iterator')

        self.capture_mode = config.get('capture_mode', 'path')
        if self.capture_mode not in ['path', 'dirname', 'filename']:
            raise ConfigurationError("Capture mode in source '%s' must be "
                                     "one of: path, dirname, filename" %
                                     name)

    def _finalizeContent(self, parent_group, items, groups):
        super()._finalizeContent(parent_group, items, groups)

        # If `capture_mode` is `dirname`, we don't need to recompute it
        # for each filename, so we do it here.
        if self.capture_mode == 'dirname':
            rel_dirpath = '.'
            if parent_group is not None:
                rel_dirpath = os.path.relpath(parent_group.spec,
                                              self.fs_endpoint_path)
            config = self._extractConfigFragment(rel_dirpath)

        for i in items:
            # Compute the config for the other capture modes.
            if self.capture_mode == 'path':
                rel_path = os.path.relpath(i.spec, self.fs_endpoint_path)
                config = self._extractConfigFragment(rel_path)
            elif self.capture_mode == 'filename':
                fname = os.path.basename(i.spec)
                config = self._extractConfigFragment(fname)

            # Set the config on the content item's metadata.
            i.metadata.setdefault('config', {}).update(config)

    def _extractConfigFragment(self, rel_path):
        raise NotImplementedError()


class AutoConfigContentSource(AutoConfigContentSourceBase):
    """ Content source that extracts configuration settings from the sub-folders
        each page resides in. This is ideal for setting tags or categories
        on pages based on the folders they're in.
    """
    SOURCE_NAME = 'autoconfig'

    def __init__(self, app, name, config):
        config['capture_mode'] = 'dirname'
        super().__init__(app, name, config)

        self.setting_name = config.get('setting_name', name)
        self.only_single_values = config.get('only_single_values', False)
        self.collapse_single_values = config.get('collapse_single_values',
                                                 False)

    def _extractConfigFragment(self, rel_path):
        if rel_path == '.':
            values = []
        else:
            values = rel_path.split(os.sep)

        if self.only_single_values:
            if len(values) > 1:
                raise Exception("Only one folder level is allowed for pages "
                                "in source '%s'." % self.name)
            elif len(values) == 1:
                values = values[0]
            else:
                values = None

        if self.collapse_single_values:
            if len(values) == 1:
                values = values[0]
            elif len(values) == 0:
                values = None

        return {self.setting_name: values}

    def findContentFromRoute(self, route_params):
        # Pages from this source are effectively flattened, so we need to
        # find pages using a brute-force kinda way.
        route_slug = route_params.get('slug', '')
        if not route_slug:
            route_slug = '_index'

        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            for f in filenames:
                slug, _ = os.path.splitext(f)
                if slug == route_slug:
                    path = os.path.join(dirpath, f)
                    metadata = self._createItemMetadata(path)
                    path = os.path.join(dirpath, f)
                    rel_path = os.path.relpath(path, self.fs_endpoint_path)
                    config = self._extractConfigFragment(rel_path)
                    metadata.setdefault('config', {}).update(config)
                    return ContentItem(path, metadata)
        return None

    def _makeSlug(self, path):
        slug = super()._makeSlug(path)
        return os.path.basename(slug)


class OrderedContentSource(AutoConfigContentSourceBase):
    """ A content source that assigns an "order" to its pages based on a
        numerical prefix in their filename. Page iterators will automatically
        sort pages using that order.
    """
    SOURCE_NAME = 'ordered'

    re_pattern = re.compile(r'(^|[/\\])(?P<num>\d+)_')

    def __init__(self, app, name, config):
        config['capture_mode'] = 'path'
        super().__init__(app, name, config)

        self.setting_name = config.get('setting_name', 'order')
        self.default_value = config.get('default_value', 0)

    def findContentFromRoute(self, route_params):
        uri_path = route_params.get('slug', '')
        if uri_path == '':
            uri_path = '_index'

        path = self.fs_endpoint_path
        uri_parts = uri_path.split('/')
        for i, p in enumerate(uri_parts):
            if i == len(uri_parts) - 1:
                # Last part, this is the filename. We need to check for either
                # the name, or the name with the prefix, but also handle a
                # possible extension.
                p_pat = r'(\d+_)?' + re.escape(p)

                _, ext = os.path.splitext(uri_path)
                if ext == '':
                    p_pat += r'\.[\w\d]+'

                found = False
                for name in os.listdir(path):
                    if re.match(p_pat, name):
                        path = os.path.join(path, name)
                        found = True
                        break
                if not found:
                    return None
            else:
                # Find each sub-directory. It can either be a directory with
                # the name itself, or the name with a number prefix.
                p_pat = r'(\d+_)?' + re.escape(p) + '$'
                found = False
                for name in os.listdir(path):
                    if re.match(p_pat, name):
                        path = os.path.join(path, name)
                        found = True
                        break
                if not found:
                    return None

        metadata = self._createItemMetadata(path)
        rel_path = os.path.relpath(path, self.fs_endpoint_path)
        config = self._extractConfigFragment(rel_path)
        metadata.setdefault('config', {}).update(config)
        return ContentItem(path, metadata)

    def getSorterIterator(self, it):
        accessor = self.getSettingAccessor()
        return OrderTrailSortIterator(it, self.setting_name + '_trail',
                                      value_accessor=accessor)

    def _finalizeContent(self, parent_group, items, groups):
        super()._finalizeContent(parent_group, items, groups)

        sn = self.setting_name
        items.sort(key=lambda i: i.metadata['config'][sn])

    def _extractConfigFragment(self, rel_path):
        values = []
        for m in self.re_pattern.finditer(rel_path):
            val = int(m.group('num'))
            values.append(val)

        if len(values) == 0:
            values.append(self.default_value)

        return {
            self.setting_name: values[-1],
            self.setting_name + '_trail': values}

    def _makeSlug(self, path):
        slug = super()._makeSlug(path)
        slug = self.re_pattern.sub(r'\1', slug)
        if slug == '_index':
            slug = ''
        return slug


class OrderTrailSortIterator(object):
    def __init__(self, it, trail_name, value_accessor):
        self.it = it
        self.trail_name = trail_name
        self.value_accessor = value_accessor

    def __iter__(self):
        return iter(sorted(self.it, key=self._key_getter))

    def _key_getter(self, item):
        values = self.value_accessor(item, self.trail_name)
        key = ''.join(map(lambda v: str(v), values))
        return key

