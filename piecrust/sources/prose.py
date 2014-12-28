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

    def buildPageFactories(self):
        factories = super(ProseSource, self).buildPageFactories()
        for f in factories:
            f.metadata['config'] = self._makeConfig(f.path)
            logger.debug(f.__dict__)
            yield f

    def findPagePath(self, metadata, mode):
        rel_path, metadata = super(ProseSource, self).findPagePath(metadata, mode)
        if rel_path:
            metadata['config'] = self._makeConfig(self.resolveRef(rel_path))
        return rel_path, metadata

    def _makeConfig(self, path):
        c = dict(self.config_recipe)
        if c.get('title') == '%first_line%':
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

