import io
import time
from werkzeug.utils import cached_property
from piecrust.configuration import ConfigurationError
from piecrust.sources.base import ContentSource, GeneratedContentException


class GeneratorSourceBase(ContentSource):
    def __init__(self, app, name, config):
        super().__init__(app, name, config)

        source_name = config.get('source')
        if source_name is None:
            raise ConfigurationError(
                "Taxonomy source '%s' requires an inner source." % name)
        self._inner_source_name = source_name

        self._raw_item = ''
        self._raw_item_time = time.time()

    @cached_property
    def inner_source(self):
        return self.app.getSource(self._inner_source_name)

    def getContents(self, group):
        # Our content is procedurally generated from other content sources,
        # so we really don't support listing anything here -- it would be
        # typically quite costly.
        raise GeneratedContentException()

    def openItem(self, item, mode='r', **kwargs):
        return io.StringIO(self._raw_item)

    def getItemMtime(self, item):
        return self._raw_item_time

