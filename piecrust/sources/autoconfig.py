import re
import os
import os.path
import glob
import logging
from piecrust.configuration import ConfigurationError
from piecrust.data.iterators import SettingSortIterator
from piecrust.sources.base import (
        SimplePageSource, IPreparingSource, SimplePaginationSourceMixin,
        PageNotFoundError, InvalidFileSystemEndpointError,
        PageFactory, MODE_CREATING, MODE_PARSING)


logger = logging.getLogger(__name__)


class AutoConfigSourceBase(SimplePageSource,
                           SimplePaginationSourceMixin):
    """ Base class for page sources that automatically apply configuration
        settings to their generated pages based on those pages' paths.
    """
    def __init__(self, app, name, config):
        super(AutoConfigSourceBase, self).__init__(app, name, config)
        self.capture_mode = config.get('capture_mode', 'path')
        if self.capture_mode not in ['path', 'dirname', 'filename']:
            raise ConfigurationError("Capture mode in source '%s' must be "
                                     "one of: path, dirname, filename" %
                                     name)

    def buildPageFactories(self):
        if not os.path.isdir(self.fs_endpoint_path):
            raise InvalidFileSystemEndpointError(self.name,
                                                 self.fs_endpoint_path)

        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            if not filenames:
                continue

            rel_dirpath = os.path.relpath(dirpath, self.fs_endpoint_path)

            # If `capture_mode` is `dirname`, we don't need to recompute it
            # for each filename, so we do it here.
            if self.capture_mode == 'dirname':
                config = self.extractConfigFragment(rel_dirpath)

            for f in filenames:
                if self.capture_mode == 'path':
                    path = os.path.join(rel_dirpath, f)
                    config = self.extractConfigFragment(path)
                elif self.capture_mode == 'filename':
                    config = self.extractConfigFragment(f)

                fac_path = f
                if rel_dirpath != '.':
                    fac_path = os.path.join(rel_dirpath, f)

                slug = self.makeSlug(rel_dirpath, f)

                metadata = {
                        'slug': slug,
                        'config': config}
                yield PageFactory(self, fac_path, metadata)

    def makeSlug(self, rel_dirpath, filename):
        raise NotImplementedError()

    def extractConfigFragment(self, rel_path):
        raise NotImplementedError()

    def findPagePath(self, metadata, mode):
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

    def makeSlug(self, rel_dirpath, filename):
        slug, ext = os.path.splitext(filename)
        if ext.lstrip('.') not in self.supported_extensions:
            slug += ext
        return slug

    def extractConfigFragment(self, rel_path):
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

    def findPagePath(self, metadata, mode):
        # Pages from this source are effectively flattened, so we need to
        # find pages using a brute-force kinda way.
        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            for f in filenames:
                slug, _ = os.path.splitext(f)
                if slug == metadata['slug']:
                    path = os.path.join(dirpath, f)
                    rel_path = os.path.relpath(path, self.fs_endpoint_path)
                    config = self.extractConfigFragment(dirpath)
                    metadata = {'slug': slug, 'config': config}
                    return rel_path, metadata


class OrderedPageSource(AutoConfigSourceBase):
    """ A page source that assigns an "order" to its pages based on a
        numerical prefix in their filename. Page iterators will automatically
        sort pages using that order.
    """
    SOURCE_NAME = 'ordered'

    re_pattern = re.compile(r'(^|/)(?P<num>\d+)_')

    def __init__(self, app, name, config):
        config['capture_mode'] = 'filename'
        super(OrderedPageSource, self).__init__(app, name, config)
        self.setting_name = config.get('setting_name', 'order')
        self.default_value = config.get('default_value', 0)
        self.supported_extensions = list(
                app.config.get('site/auto_formats').keys())

    def makeSlug(self, rel_dirpath, filename):
        slug, ext = os.path.splitext(filename)
        if ext.lstrip('.') not in self.supported_extensions:
            slug += ext
        slug = self.re_pattern.sub(r'\1', slug)
        slug = os.path.join(rel_dirpath, slug).replace('\\', '/')
        if slug.startswith('./'):
            slug = slug[2:]
        return slug

    def extractConfigFragment(self, rel_path):
        m = self.re_pattern.match(rel_path)
        if m is not None:
            val = int(m.group('num'))
        else:
            val = self.default_value
        return {self.setting_name: val}

    def findPagePath(self, metadata, mode):
        uri_path = metadata.get('slug', '')
        if uri_path != '':
            uri_parts = ['*_%s' % p for p in uri_path.split('/')]
        else:
            uri_parts = ['*__index']
        uri_parts.insert(0, self.fs_endpoint_path)
        path = os.path.join(*uri_parts)

        _, ext = os.path.splitext(uri_path)
        if ext == '':
            path += '.*'

        possibles = glob.glob(path)

        if len(possibles) == 0:
            return None, None

        if len(possibles) > 1:
            raise Exception("More than one path matching: %s" % uri_path)

        path = possibles[0]
        fac_path = os.path.relpath(path, self.fs_endpoint_path)

        _, filename = os.path.split(path)
        config = self.extractConfigFragment(filename)
        metadata = {'slug': uri_path, 'config': config}

        return fac_path, metadata

    def getSorterIterator(self, it):
        accessor = self.getSettingAccessor()
        return SettingSortIterator(it, self.setting_name,
                                   value_accessor=accessor)

    def _populateMetadata(self, rel_path, metadata, mode=None):
        _, filename = os.path.split(rel_path)
        config = self.extractConfigFragment(filename)
        metadata['config'] = config
        slug = metadata['slug']
        metadata['slug'] = self.re_pattern.sub(r'\1', slug)

