import re
import os
import os.path
import logging
from piecrust.configuration import ConfigurationError
from piecrust.sources.base import (
        PageSource, PageFactory, InvalidFileSystemEndpointError)
from piecrust.sources.default import (
        filter_page_dirname, filter_page_filename)
from piecrust.sources.interfaces import IListableSource
from piecrust.sources.mixins import SimplePaginationSourceMixin


logger = logging.getLogger(__name__)


class AutoConfigSourceBase(PageSource, SimplePaginationSourceMixin,
                           IListableSource):
    """ Base class for page sources that automatically apply configuration
        settings to their generated pages based on those pages' paths.
    """
    def __init__(self, app, name, config):
        super(AutoConfigSourceBase, self).__init__(app, name, config)
        self.fs_endpoint = config.get('fs_endpoint', name)
        self.fs_endpoint_path = os.path.join(self.root_dir, self.fs_endpoint)
        self.supported_extensions = list(
                app.config.get('site/auto_formats').keys())
        self.default_auto_format = app.config.get('site/default_auto_format')

        self.capture_mode = config.get('capture_mode', 'path')
        if self.capture_mode not in ['path', 'dirname', 'filename']:
            raise ConfigurationError("Capture mode in source '%s' must be "
                                     "one of: path, dirname, filename" %
                                     name)

    def buildPageFactories(self):
        logger.debug("Scanning for pages in: %s" % self.fs_endpoint_path)
        if not os.path.isdir(self.fs_endpoint_path):
            raise InvalidFileSystemEndpointError(self.name,
                                                 self.fs_endpoint_path)

        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            rel_dirpath = os.path.relpath(dirpath, self.fs_endpoint_path)
            dirnames[:] = list(filter(filter_page_dirname, dirnames))

            # If `capture_mode` is `dirname`, we don't need to recompute it
            # for each filename, so we do it here.
            if self.capture_mode == 'dirname':
                config = self._extractConfigFragment(rel_dirpath)

            for f in filter(filter_page_filename, filenames):
                if self.capture_mode == 'path':
                    path = os.path.join(rel_dirpath, f)
                    config = self._extractConfigFragment(path)
                elif self.capture_mode == 'filename':
                    config = self._extractConfigFragment(f)

                fac_path = f
                if rel_dirpath != '.':
                    fac_path = os.path.join(rel_dirpath, f)

                slug = self._makeSlug(fac_path)

                metadata = {
                        'slug': slug,
                        'config': config}
                yield PageFactory(self, fac_path, metadata)

    def resolveRef(self, ref_path):
        path = os.path.normpath(
                os.path.join(self.fs_endpoint_path, ref_path.lstrip("\\/")))

        config = None
        if self.capture_mode == 'dirname':
            config = self._extractConfigFragment(os.path.dirname(ref_path))
        elif self.capture_mode == 'path':
            config = self._extractConfigFragment(ref_path)
        elif self.capture_mode == 'filename':
            config = self._extractConfigFragment(os.path.basename(ref_path))

        slug = self._makeSlug(ref_path)
        metadata = {'slug': slug, 'config': config}
        return path, metadata

    def listPath(self, rel_path):
        raise NotImplementedError()

    def getDirpath(self, rel_path):
        return os.path.dirname(rel_path)

    def getBasename(self, rel_path):
        filename = os.path.basename(rel_path)
        name, _ = os.path.splitext(filename)
        return name

    def _makeSlug(self, rel_path):
        slug = rel_path.replace('\\', '/')
        slug = self._cleanSlug(slug)
        slug, ext = os.path.splitext(slug)
        if ext.lstrip('.') not in self.supported_extensions:
            slug += ext
        if slug.startswith('./'):
            slug = slug[2:]
        if slug == '_index':
            slug = ''
        return slug

    def _cleanSlug(self, slug):
        return slug

    def _extractConfigFragment(self, rel_path):
        raise NotImplementedError()


class AutoConfigSource(AutoConfigSourceBase):
    """ Page source that extracts configuration settings from the sub-folders
        each page resides in. This is ideal for setting tags or categories
        on pages based on the folders they're in.
    """
    SOURCE_NAME = 'autoconfig'

    def __init__(self, app, name, config):
        config['capture_mode'] = 'dirname'
        super(AutoConfigSource, self).__init__(app, name, config)
        self.setting_name = config.get('setting_name', name)
        self.only_single_values = config.get('only_single_values', False)
        self.collapse_single_values = config.get('collapse_single_values',
                                                 False)
        self.supported_extensions = list(
                app.config.get('site/auto_formats').keys())

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

    def findPageFactory(self, metadata, mode):
        # Pages from this source are effectively flattened, so we need to
        # find pages using a brute-force kinda way.
        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            for f in filenames:
                slug, _ = os.path.splitext(f)
                if slug == metadata['slug']:
                    path = os.path.join(dirpath, f)
                    rel_path = os.path.relpath(path, self.fs_endpoint_path)
                    config = self._extractConfigFragment(rel_path)
                    metadata = {'slug': slug, 'config': config}
                    return PageFactory(self, rel_path, metadata)
        return None

    def listPath(self, rel_path):
        rel_path = rel_path.lstrip('\\/')
        path = os.path.join(self.fs_endpoint_path, rel_path)
        names = sorted(os.listdir(path))
        items = []
        for name in names:
            if os.path.isdir(os.path.join(path, name)):
                if filter_page_dirname(name):
                    rel_subdir = os.path.join(rel_path, name)
                    items.append((True, name, rel_subdir))
            else:
                if filter_page_filename(name):
                    cur_rel_path = os.path.join(rel_path, name)
                    slug = self._makeSlug(cur_rel_path)
                    config = self._extractConfigFragment(cur_rel_path)
                    metadata = {'slug': slug, 'config': config}
                    fac = PageFactory(self, cur_rel_path, metadata)

                    name, _ = os.path.splitext(name)
                    items.append((False, name, fac))
        return items

    def _cleanSlug(self, slug):
        return os.path.basename(slug)


class OrderedPageSource(AutoConfigSourceBase):
    """ A page source that assigns an "order" to its pages based on a
        numerical prefix in their filename. Page iterators will automatically
        sort pages using that order.
    """
    SOURCE_NAME = 'ordered'

    re_pattern = re.compile(r'(^|[/\\])(?P<num>\d+)_')

    def __init__(self, app, name, config):
        config['capture_mode'] = 'path'
        super(OrderedPageSource, self).__init__(app, name, config)
        self.setting_name = config.get('setting_name', 'order')
        self.default_value = config.get('default_value', 0)
        self.supported_extensions = list(
                app.config.get('site/auto_formats').keys())

    def findPageFactory(self, metadata, mode):
        uri_path = metadata.get('slug', '')
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
                p_pat = r'(\d+_)?' + re.escape(p)
                found = False
                for name in os.listdir(path):
                    if re.match(p_pat, name):
                        path = os.path.join(path, name)
                        found = True
                        break
                if not found:
                    return None

        fac_path = os.path.relpath(path, self.fs_endpoint_path)
        config = self._extractConfigFragment(fac_path)
        metadata = {'slug': uri_path, 'config': config}

        return PageFactory(self, fac_path, metadata)

    def getSorterIterator(self, it):
        accessor = self.getSettingAccessor()
        return OrderTrailSortIterator(it, self.setting_name + '_trail',
                                      value_accessor=accessor)

    def listPath(self, rel_path):
        rel_path = rel_path.lstrip('/')
        path = self.fs_endpoint_path
        if rel_path != '':
            parts = rel_path.split('/')
            for p in parts:
                p_pat = r'(\d+_)?' + re.escape(p) + '$'
                for name in os.listdir(path):
                    if re.match(p_pat, name):
                        path = os.path.join(path, name)
                        break
                else:
                    raise Exception("No such path: %s" % rel_path)

        items = []
        names = sorted(os.listdir(path))
        for name in names:
            clean_name = self.re_pattern.sub('', name)
            clean_name, _ = os.path.splitext(clean_name)
            if os.path.isdir(os.path.join(path, name)):
                if filter_page_dirname(name):
                    rel_subdir = os.path.join(rel_path, name)
                    items.append((True, clean_name, rel_subdir))
            else:
                if filter_page_filename(name):
                    slug = self._makeSlug(os.path.join(rel_path, name))

                    fac_path = name
                    if rel_path != '.':
                        fac_path = os.path.join(rel_path, name)
                    fac_path = fac_path.replace('\\', '/')

                    config = self._extractConfigFragment(fac_path)
                    metadata = {'slug': slug, 'config': config}
                    fac = PageFactory(self, fac_path, metadata)

                    name, _ = os.path.splitext(name)
                    items.append((False, clean_name, fac))
        return items

    def _cleanSlug(self, slug):
        return self.re_pattern.sub(r'\1', slug)

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

    def _populateMetadata(self, rel_path, metadata, mode=None):
        _, filename = os.path.split(rel_path)
        config = self._extractConfigFragment(filename)
        metadata['config'] = config
        slug = metadata['slug']
        metadata['slug'] = self.re_pattern.sub(r'\1', slug)


class OrderTrailSortIterator(object):
    def __init__(self, it, trail_name, value_accessor):
        self.it = it
        self.trail_name = trail_name
        self.value_accessor = value_accessor

    def __iter__(self):
        return iter(sorted(self.it, key=self._key_getter))

    def _key_getter(self, item):
        values = self.value_accessor(item, self.trail_name)
        key = ''.join(values)
        return key

