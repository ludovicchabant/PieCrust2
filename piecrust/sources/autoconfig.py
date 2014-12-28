import os
import os.path
import logging
from piecrust.sources.base import (
        SimplePageSource, IPreparingSource, SimplePaginationSourceMixin,
        PageNotFoundError, InvalidFileSystemEndpointError,
        PageFactory, MODE_CREATING, MODE_PARSING)


logger = logging.getLogger(__name__)


class AutoConfigSource(SimplePageSource,
                       SimplePaginationSourceMixin):
    SOURCE_NAME = 'autoconfig'

    def __init__(self, app, name, config):
        super(AutoConfigSource, self).__init__(app, name, config)
        self.setting_name = config.get('setting_name', name)
        self.collapse_single_values = config.get('collapse_single_values', False)
        self.only_single_values = config.get('only_single_values', False)

    def buildPageFactories(self):
        if not os.path.isdir(self.fs_endpoint_path):
            raise InvalidFileSystemEndpointError(self.name, self.fs_endpoint_path)

        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            if not filenames:
                continue
            config = self._extractConfigFragment(dirpath)
            for f in filenames:
                slug, ext = os.path.splitext(f)
                path = os.path.join(dirpath, f)
                metadata = {
                        'slug': slug,
                        'config': config}
                yield PageFactory(self, path, metadata)

    def _extractConfigFragment(self, path):
        rel_path = os.path.relpath(path, self.fs_endpoint_path)
        if rel_path == '.':
            values = []
        else:
            values = rel_path.split(os.sep)
        if self.only_single_values and len(values) > 1:
            raise Exception("Only one folder level is allowed for pages "
                            "in source '%s'." % self.name)
        if self.collapse_single_values and len(values) == 1:
            values = values[0]
        return {self.setting_name: values}

    def findPagePath(self, metadata, mode):
        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            for f in filenames:
                slug, _ = os.path.splitext(f)
                if slug == metadata['slug']:
                    path = os.path.join(dirpath, f)
                    rel_path = os.path.relpath(path, self.fs_endpoint_path)
                    config = self._extractConfigFragment(dirpath)
                    metadata = {'slug': slug, 'config': config}
                    return rel_path, metadata

