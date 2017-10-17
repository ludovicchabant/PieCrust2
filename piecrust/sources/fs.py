import os.path
import re
import glob
import fnmatch
import logging
from piecrust import osutil
from piecrust.routing import RouteParameter
from piecrust.sources.base import (
    ContentItem, ContentGroup, ContentSource,
    REL_PARENT_GROUP, REL_LOGICAL_PARENT_ITEM, REL_LOGICAl_CHILD_GROUP)


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

    @property
    def root_dir(self):
        if self.is_theme_source:
            return self.app.theme_dir
        return self.app.root_dir

    def _checkFSEndpoint(self):
        if not os.path.isdir(self.fs_endpoint_path):
            if self.config.get('ignore_missing_dir'):
                return False
            raise InvalidFileSystemEndpointError(self.name,
                                                 self.fs_endpoint_path)
        return True

    def openItem(self, item, mode='r', **kwargs):
        for m in 'wxa+':
            if m in mode:
                # If opening the file for writing, let's make sure the
                # directory exists.
                dirname = os.path.dirname(item.spec)
                if not os.path.exists(dirname):
                    os.makedirs(dirname, 0o755)
                break
        return open(item.spec, mode, **kwargs)

    def getItemMtime(self, item):
        return os.path.getmtime(item.spec)

    def describe(self):
        return {'endpoint_path': self.fs_endpoint_path}


class FSContentSource(FSContentSourceBase):
    """ Implements a `ContentSource` that simply returns files on disk
        under a given root directory.
    """
    SOURCE_NAME = 'fs'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)

        config.setdefault('data_type', 'asset_iterator')

        ig, ir = _parse_ignores(config.get('ignore'))
        self._ignore_globs = ig
        self._ignore_regexes = ir

    def getContents(self, group):
        if not self._checkFSEndpoint():
            return None

        parent_path = self.fs_endpoint_path
        if group is not None:
            parent_path = group.spec

        names = filter(_filter_crap_files, osutil.listdir(parent_path))

        final_names = []
        for name in names:
            path = os.path.join(parent_path, name)
            if not self._filterIgnored(path):
                final_names.append(name)

        items = []
        groups = []
        for name in final_names:
            path = os.path.join(parent_path, name)
            if os.path.isdir(path):
                metadata = self._createGroupMetadata(path)
                groups.append(ContentGroup(path, metadata))
            else:
                metadata = self._createItemMetadata(path)
                items.append(ContentItem(path, metadata))
        self._finalizeContent(group, items, groups)
        return items + groups

    def _filterIgnored(self, path):
        rel_path = os.path.relpath(path, self.fs_endpoint_path)
        for g in self._ignore_globs:
            if fnmatch.fnmatch(rel_path, g):
                return True
        for r in self._ignore_regexes:
            if r.search(g):
                return True
        return False

    def _createGroupMetadata(self, path):
        return {}

    def _createItemMetadata(self, path):
        return {}

    def _finalizeContent(self, parent_group, items, groups):
        pass

    def findGroup(self, rel_spec):
        path = os.path.join(self.fs_endpoint_path, rel_spec)
        if os.path.isdir(path):
            metadata = self._createGroupMetadata(path)
            return ContentGroup(path, metadata)
        return None

    def getRelatedContents(self, item, relationship):
        if relationship == REL_PARENT_GROUP:
            parent_dir = os.path.dirname(item.spec)
            if len(parent_dir) >= len(self.fs_endpoint_path):
                metadata = self._createGroupMetadata(parent_dir)
                return ContentGroup(parent_dir, metadata)

            # Don't return a group for paths that are outside of our
            # endpoint directory.
            return None

        if relationship == REL_LOGICAL_PARENT_ITEM:
            # If we want the logical parent item of a folder, we find a
            # page file with the same name as the folder.
            if not item.is_group:
                raise ValueError()
            parent_glob = os.path.join(item.spec, '*')
            for n in glob.iglob(parent_glob):
                if os.path.isfile(n):
                    metadata = self._createItemMetadata(n)
                    return ContentItem(n, metadata)
            return None

        if relationship == REL_LOGICAl_CHILD_GROUP:
            # If we want the children items of an item, we look for
            # a directory that has the same name as the item's file.
            if item.is_group:
                raise ValueError()
            dir_path, _ = os.path.splitext(item.spec)
            if os.path.isdir(dir_path):
                metadata = self._createGroupMetadata(dir_path)
                return ContentGroup(dir_path, metadata)
            return None

        return None

    def getSupportedRouteParameters(self):
        return [
            RouteParameter('path', RouteParameter.TYPE_PATH)]


def _parse_ignores(patterns):
    globs = []
    regexes = []
    if patterns:
        for pat in patterns:
            if len(pat) > 2 and pat[0] == '/' and pat[-1] == '/':
                regexes.append(re.compile(pat[1:-1]))
            else:
                globs.append(pat)
    return globs, regexes
