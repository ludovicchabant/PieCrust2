import os
import os.path
import logging
from piecrust.sources.base import (
        PageFactory, PageSource, InvalidFileSystemEndpointError,
        MODE_CREATING)
from piecrust.sources.interfaces import IListableSource, IPreparingSource
from piecrust.sources.mixins import SimplePaginationSourceMixin


logger = logging.getLogger(__name__)


def filter_page_dirname(d):
    return not (d.startswith('.') or d.endswith('-assets'))


def filter_page_filename(f):
    return (f[0] != '.' and   # .DS_store and other crap
            f[-1] != '~' and  # Vim temp files and what-not
            f not in ['Thumbs.db'])  # Windows bullshit


class DefaultPageSource(PageSource, IListableSource, IPreparingSource,
                        SimplePaginationSourceMixin):
    SOURCE_NAME = 'default'

    def __init__(self, app, name, config):
        super(DefaultPageSource, self).__init__(app, name, config)
        self.fs_endpoint = config.get('fs_endpoint', name)
        self.fs_endpoint_path = os.path.join(self.root_dir, self.fs_endpoint)
        self.supported_extensions = list(
                app.config.get('site/auto_formats').keys())
        self.default_auto_format = app.config.get('site/default_auto_format')

    def buildPageFactories(self):
        logger.debug("Scanning for pages in: %s" % self.fs_endpoint_path)
        if not os.path.isdir(self.fs_endpoint_path):
            if self.ignore_missing_dir:
                return
            raise InvalidFileSystemEndpointError(self.name,
                                                 self.fs_endpoint_path)

        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            rel_dirpath = os.path.relpath(dirpath, self.fs_endpoint_path)
            dirnames[:] = list(filter(filter_page_dirname, dirnames))
            for f in sorted(filter(filter_page_filename, filenames)):
                fac_path = f
                if rel_dirpath != '.':
                    fac_path = os.path.join(rel_dirpath, f)
                slug = self._makeSlug(fac_path)
                metadata = {'slug': slug}
                fac_path = fac_path.replace('\\', '/')
                self._populateMetadata(fac_path, metadata)
                yield PageFactory(self, fac_path, metadata)

    def resolveRef(self, ref_path):
        path = os.path.normpath(
                os.path.join(self.fs_endpoint_path, ref_path.lstrip("\\/")))
        slug = self._makeSlug(ref_path)
        metadata = {'slug': slug}
        self._populateMetadata(ref_path, metadata)
        return path, metadata

    def findPageFactory(self, metadata, mode):
        uri_path = metadata.get('slug', '')
        if not uri_path:
            uri_path = '_index'
        path = os.path.join(self.fs_endpoint_path, uri_path)
        _, ext = os.path.splitext(path)

        if mode == MODE_CREATING:
            if ext == '':
                path = '%s.%s' % (path, self.default_auto_format)
            rel_path = os.path.relpath(path, self.fs_endpoint_path)
            rel_path = rel_path.replace('\\', '/')
            self._populateMetadata(rel_path, metadata, mode)
            return PageFactory(self, rel_path, metadata)

        if ext == '':
            paths_to_check = [
                    '%s.%s' % (path, e)
                    for e in self.supported_extensions]
        else:
            paths_to_check = [path]
        for path in paths_to_check:
            if os.path.isfile(path):
                rel_path = os.path.relpath(path, self.fs_endpoint_path)
                rel_path = rel_path.replace('\\', '/')
                self._populateMetadata(rel_path, metadata, mode)
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
                    slug = self._makeSlug(os.path.join(rel_path, name))
                    metadata = {'slug': slug}

                    fac_path = name
                    if rel_path != '.':
                        fac_path = os.path.join(rel_path, name)
                    fac_path = fac_path.replace('\\', '/')

                    self._populateMetadata(fac_path, metadata)
                    fac = PageFactory(self, fac_path, metadata)

                    name, _ = os.path.splitext(name)
                    items.append((False, name, fac))
        return items

    def getDirpath(self, rel_path):
        return os.path.dirname(rel_path)

    def getBasename(self, rel_path):
        filename = os.path.basename(rel_path)
        name, _ = os.path.splitext(filename)
        return name

    def setupPrepareParser(self, parser, app):
        parser.add_argument('uri', help='The URI for the new page.')

    def buildMetadata(self, args):
        return {'slug': args.uri}

    def _makeSlug(self, rel_path):
        slug, ext = os.path.splitext(rel_path)
        slug = slug.replace('\\', '/')
        if ext.lstrip('.') not in self.supported_extensions:
            slug += ext
        if slug.startswith('./'):
            slug = slug[2:]
        if slug == '_index':
            slug = ''
        return slug

    def _populateMetadata(self, rel_path, metadata, mode=None):
        pass

