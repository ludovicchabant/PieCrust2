import os
import os.path
import logging
from piecrust.sources.base import (
        SimplePageSource, SimplePaginationSourceMixin)


logger = logging.getLogger(__name__)


class ProseSource(SimplePageSource,
                  SimplePaginationSourceMixin):
    SOURCE_NAME = 'prose'

    def __init__(self, app, name, config):
        super(ProseSource, self).__init__(app, name, config)
        self.config_recipe = config.get('config', {})

    def _populateMetadata(self, rel_path, metadata):
        metadata['config'] = self._makeConfig(rel_path)

    def _makeConfig(self, rel_path):
        c = dict(self.config_recipe)
        if c.get('title') == '%first_line%':
            path = os.path.join(self.fs_endpoint_path, rel_path)
            c['title'] = get_first_line(path)
        return c


def get_first_line(path):
    with open(path, 'r') as f:
        while True:
            l = f.readline()
            if not l:
                break
            l = l.strip()
            if not l:
                continue
            return l
    return None

