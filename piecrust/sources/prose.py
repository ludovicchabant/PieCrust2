import os
import os.path
import copy
import logging
from piecrust.sources.base import MODE_CREATING, MODE_PARSING
from piecrust.sources.default import DefaultPageSource


logger = logging.getLogger(__name__)


class ProseSource(DefaultPageSource):
    SOURCE_NAME = 'prose'

    def __init__(self, app, name, config):
        super(ProseSource, self).__init__(app, name, config)
        self.config_recipe = config.get('config', {})

    def _populateMetadata(self, rel_path, metadata, mode=None):
        metadata['config'] = self._makeConfig(rel_path, mode)

    def _makeConfig(self, rel_path, mode):
        c = copy.deepcopy(self.config_recipe)
        if c.get('title') == '%first_line%' and mode != MODE_CREATING:
            path = os.path.join(self.fs_endpoint_path, rel_path)
            try:
                c['title'] = get_first_line(path)
            except OSError:
                if mode == MODE_PARSING:
                    raise
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

