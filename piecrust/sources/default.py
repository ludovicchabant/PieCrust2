import os.path
import logging
from piecrust.routing import RouteParameter
from piecrust.sources.base import REL_ASSETS, ContentItem
from piecrust.sources.fs import FSContentSource
from piecrust.sources.interfaces import (
    IPreparingSource, IInteractiveSource, InteractiveField)
from piecrust.sources.mixins import SimpleAssetsSubDirMixin
from piecrust.uriutil import uri_to_title


logger = logging.getLogger(__name__)


class DefaultContentSource(FSContentSource,
                           SimpleAssetsSubDirMixin,
                           IPreparingSource, IInteractiveSource):
    SOURCE_NAME = 'default'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)
        self.auto_formats = app.config.get('site/auto_formats')
        self.default_auto_format = app.config.get('site/default_auto_format')
        self.supported_extensions = list(self.auto_formats)

    def _createItemMetadata(self, path):
        return self._doCreateItemMetadata(path)

    def _finalizeContent(self, parent_group, items, groups):
        SimpleAssetsSubDirMixin._onFinalizeContent(
            self, parent_group, items, groups)

    def _doCreateItemMetadata(self, path):
        slug = self._makeSlug(path)
        metadata = {
            'slug': slug
        }
        _, ext = os.path.splitext(path)
        if ext:
            fmt = self.auto_formats.get(ext.lstrip('.'))
            if fmt:
                metadata['config'] = {'format': fmt}
        return metadata

    def _makeSlug(self, path):
        rel_path = os.path.relpath(path, self.fs_endpoint_path)
        slug, ext = os.path.splitext(rel_path)
        slug = slug.replace('\\', '/')
        if ext.lstrip('.') not in self.supported_extensions:
            slug += ext
        if slug.startswith('./'):
            slug = slug[2:]
        if slug == '_index':
            slug = ''
        return slug

    def getRelatedContents(self, item, relationship):
        if relationship == REL_ASSETS:
            SimpleAssetsSubDirMixin._getRelatedAssetsContents(self, item)
        raise NotImplementedError()

    def getSupportedRouteParameters(self):
        return [
            RouteParameter('slug', RouteParameter.TYPE_PATH)]

    def findContent(self, route_params):
        uri_path = route_params.get('slug', '')
        if not uri_path:
            uri_path = '_index'
        path = os.path.join(self.fs_endpoint_path, uri_path)
        _, ext = os.path.splitext(path)

        if ext == '':
            paths_to_check = [
                '%s.%s' % (path, e)
                for e in self.supported_extensions]
        else:
            paths_to_check = [path]
        for path in paths_to_check:
            if os.path.isfile(path):
                metadata = self._doCreateItemMetadata(path)
                return ContentItem(path, metadata)
        return None

    def setupPrepareParser(self, parser, app):
        parser.add_argument('uri', help='The URI for the new page.')

    def createContent(self, args):
        if not hasattr(args, 'uri'):
            uri = None
        else:
            uri = args.uri
        if not uri:
            uri = '_index'
        path = os.path.join(self.fs_endpoint_path, uri)
        _, ext = os.path.splitext(path)
        if ext == '':
            path = '%s.%s' % (path, self.default_auto_format)

        metadata = self._doCreateItemMetadata(path)
        config = metadata.setdefault('config', {})
        config.update({'title': uri_to_title(
            os.path.basename(metadata['slug']))})
        return ContentItem(path, metadata)

    def getInteractiveFields(self):
        return [
            InteractiveField('slug', InteractiveField.TYPE_STRING,
                             'new-page')]
