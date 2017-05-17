import os.path
import logging
from piecrust import osutil
from piecrust.routing import RouteParameter
from piecrust.sources.base import ContentItem, ContentGroup, ContentSource


logger = logging.getLogger(__name__)


class InvalidFileSystemEndpointError(Exception):
    def __init__(self, source_name, fs_endpoint):
        super(InvalidFileSystemEndpointError, self).__init__(
            "Invalid file-system endpoint for source '%s': %s" %
            (source_name, fs_endpoint))


def _filter_crap_files(f):
    return (f[-1] != '~' and  # Vim temp files and what-not
            f not in ['.DS_Store', 'Thumbs.db'])  # OSX and Windows bullshit


class FSContentSourceBase(ContentSource):
    """ Implements some basic stuff for a `ContentSource` that stores its
        items as files on disk.
    """
    def __init__(self, app, name, config):
        super().__init__(app, name, config)
        self.fs_endpoint = config.get('fs_endpoint', name)
        self.fs_endpoint_path = os.path.join(self.root_dir, self.fs_endpoint)
        self._fs_filter = None

    def _checkFSEndpoint(self):
        if not os.path.isdir(self.fs_endpoint_path):
            if self.config.get('ignore_missing_dir'):
                return False
            raise InvalidFileSystemEndpointError(self.name,
                                                 self.fs_endpoint_path)
        return True

    def openItem(self, item, mode='r'):
        for m in 'wxa+':
            if m in mode:
                # If opening the file for writing, let's make sure the
                # directory exists.
                dirname = os.path.dirname(item.spec)
                if not os.path.exists(dirname):
                    os.makedirs(dirname, 0o755)
                break
        return open(item.spec, mode)

    def getItemMtime(self, item):
        return os.path.getmtime(item.spec)


class FSContentSource(FSContentSourceBase):
    """ Implements a `ContentSource` that simply returns files on disk
        under a given root directory.
    """
    SOURCE_NAME = 'fs'

    def getContents(self, group):
        logger.debug("Scanning for content in: %s" % self.fs_endpoint_path)
        if not self._checkFSEndpoint():
            return None

        parent_path = self.fs_endpoint_path
        if group is not None:
            parent_path = group.spec

        names = filter(_filter_crap_files, osutil.listdir(parent_path))
        if self._fs_filter is not None:
            names = filter(self._fs_filter, names)

        items = []
        groups = []
        for name in names:
            path = os.path.join(parent_path, name)
            if os.path.isdir(path):
                metadata = self._createGroupMetadata(path)
                groups.append(ContentGroup(path, metadata))
            else:
                metadata = self._createItemMetadata(path)
                items.append(ContentItem(path, metadata))
        self._finalizeContent(group, items, groups)
        return items + groups

    def _createGroupMetadata(self, path):
        return {}

    def _createItemMetadata(self, path):
        return {}

    def _finalizeContent(self, parent_group, items, groups):
        pass

    def getRelatedContents(self, item, relationship):
        return None

    def findContent(self, route_params):
        rel_path = route_params['path']
        path = os.path.join(self.fs_endpoint_path, rel_path)
        metadata = self._createItemMetadata(path)
        return ContentItem(path, metadata)

    def getSupportedRouteParameters(self):
        return [
            RouteParameter('path', RouteParameter.TYPE_PATH)]

    def describe(self):
        return {'endpoint_path': self.fs_endpoint_path}
