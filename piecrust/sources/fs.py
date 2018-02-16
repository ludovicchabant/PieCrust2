import os.path
import re
import glob
import fnmatch
import logging
from piecrust import osutil
from piecrust.routing import RouteParameter
from piecrust.sources.base import (
    ContentItem, ContentGroup, ContentSource,
    REL_PARENT_GROUP, REL_LOGICAL_PARENT_ITEM, REL_LOGICAL_CHILD_GROUP)


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

        self._ignore = _parse_patterns(config.get('ignore'))
        self._filter = _parse_patterns(config.get('filter'))

    def getContents(self, group):
        if not self._checkFSEndpoint():
            return None

        parent_path = self.fs_endpoint_path
        if group is not None:
            parent_path = group.spec

        names = filter(_filter_crap_files, osutil.listdir(parent_path))

        items = []
        groups = []
        for name in names:
            path = os.path.join(parent_path, name)
            if self._filterPath(path):
                if os.path.isdir(path):
                    metadata = self._createGroupMetadata(path)
                    groups.append(ContentGroup(path, metadata))
                else:
                    metadata = self._createItemMetadata(path)
                    items.append(ContentItem(path, metadata))
        self._finalizeContent(group, items, groups)
        return items + groups

    def _filterPath(self, path):
        rel_path = os.path.relpath(path, self.fs_endpoint_path)

        if self._ignore is not None:
            if _matches_patterns(self._ignore, rel_path):
                return False

        if self._filter is not None:
            if _matches_patterns(self._filter, rel_path):
                return True
            return False

        return True

    def _createGroupMetadata(self, path):
        return {}

    def _createItemMetadata(self, path):
        return {}

    def _finalizeContent(self, parent_group, items, groups):
        pass

    def findContentFromSpec(self, spec):
        if os.path.isdir(spec):
            metadata = self._createGroupMetadata(spec)
            return ContentGroup(spec, metadata)
        elif os.path.isfile(spec):
            metadata = self._createItemMetadata(spec)
            return ContentItem(spec, metadata)
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
            parent_glob = item.spec.rstrip('/\\') + '.*'
            for n in glob.iglob(parent_glob):
                if os.path.isfile(n):
                    metadata = self._createItemMetadata(n)
                    return ContentItem(n, metadata)
            return None

        if relationship == REL_LOGICAL_CHILD_GROUP:
            # If we want the children items of an item, we look for
            # a directory that has the same name as the item's file.
            if item.is_group:
                raise ValueError(
                    "'%s' is a content group and doesn't have a logical "
                    "child. Did you call `family.children` on a group? "
                    "You need to check `is_group` first.")
            dir_path, _ = os.path.splitext(item.spec)
            if os.path.isdir(dir_path):
                metadata = self._createGroupMetadata(dir_path)
                return ContentGroup(dir_path, metadata)
            return None

        return None

    def getSupportedRouteParameters(self):
        return [
            RouteParameter('path', RouteParameter.TYPE_PATH)]


def _parse_patterns(patterns):
    if not patterns:
        return None

    globs = []
    regexes = []
    for pat in patterns:
        if len(pat) > 2 and pat[0] == '/' and pat[-1] == '/':
            regexes.append(re.compile(pat[1:-1]))
        else:
            globs.append(pat)
    return globs, regexes


def _matches_patterns(patterns, subj):
    globs, regexes = patterns
    if globs:
        for g in globs:
            if fnmatch.fnmatch(subj, g):
                return True
    if regexes:
        for r in regexes:
            if r.search(subj):
                return True
    return False
