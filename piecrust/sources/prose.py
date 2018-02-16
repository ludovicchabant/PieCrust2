import copy
import logging
from piecrust.sources.default import DefaultContentSource


logger = logging.getLogger(__name__)


class ProseSource(DefaultContentSource):
    SOURCE_NAME = 'prose'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)
        self.config_recipe = config.get('config', {})

    def _createItemMetadata(self, path):
        metadata = super()._createItemMetadata(path)
        config = metadata.setdefault('config', {})
        config.update(self._makeConfig(path))
        return metadata

    def _makeConfig(self, path):
        c = copy.deepcopy(self.config_recipe)
        if c.get('title') == '%first_line%':
            c['title'] = get_first_line(path)
        return c


def get_first_line(path):
    with open(path, 'r') as f:
        while True:
            line = f.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            return line
    return None

