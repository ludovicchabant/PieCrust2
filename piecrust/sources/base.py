import copy
import logging
from werkzeug.utils import cached_property
from piecrust.page import Page
from piecrust.data.assetor import Assetor


REALM_USER = 0
REALM_THEME = 1
REALM_NAMES = {
        REALM_USER: 'User',
        REALM_THEME: 'Theme'}


MODE_PARSING = 0
MODE_CREATING = 1


logger = logging.getLogger(__name__)


def build_pages(app, factories):
    for f in factories:
        yield f.buildPage()


class SourceNotFoundError(Exception):
    pass


class InvalidFileSystemEndpointError(Exception):
    def __init__(self, source_name, fs_endpoint):
        super(InvalidFileSystemEndpointError, self).__init__(
                "Invalid file-system endpoint for source '%s': %s" %
                (source_name, fs_endpoint))


class PageFactory(object):
    """ A class responsible for creating a page.
    """
    def __init__(self, source, rel_path, metadata):
        self.source = source
        self.rel_path = rel_path
        self.metadata = metadata

    @cached_property
    def ref_spec(self):
        return '%s:%s' % (self.source.name, self.rel_path)

    @cached_property
    def path(self):
        path, _ = self.source.resolveRef(self.rel_path)
        return path

    def buildPage(self):
        repo = self.source.app.env.page_repository
        cache_key = '%s:%s' % (self.source.name, self.rel_path)
        return repo.get(cache_key, self._doBuildPage)

    def _doBuildPage(self):
        logger.debug("Building page: %s" % self.path)
        page = Page(self.source, copy.deepcopy(self.metadata), self.rel_path)
        return page


class PageSource(object):
    """ A source for pages, e.g. a directory with one file per page.
    """
    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config or {}
        self.config.setdefault('realm', REALM_USER)
        self._factories = None
        self._provider_type = None

    def __getattr__(self, name):
        try:
            return self.config[name]
        except KeyError:
            raise AttributeError()

    @property
    def is_theme_source(self):
        return self.realm == REALM_THEME

    @property
    def root_dir(self):
        if self.is_theme_source:
            return self.app.theme_dir
        return self.app.root_dir

    def getPages(self):
        return build_pages(self.app, self.getPageFactories())

    def getPage(self, metadata):
        factory = self.findPageFactory(metadata, MODE_PARSING)
        if factory is None:
            return None
        return factory.buildPage()

    def getPageFactories(self):
        if self._factories is None:
            self._factories = list(self.buildPageFactories())
        return self._factories

    def getSupportedRouteParameters(self):
        raise NotImplementedError()

    def buildPageFactories(self):
        raise NotImplementedError()

    def buildPageFactory(self, path):
        raise NotImplementedError()

    def resolveRef(self, ref_path):
        """ Returns the full path and source metadata given a source
            (relative) path, like a ref-spec.
        """
        raise NotImplementedError()

    def findPageFactory(self, metadata, mode):
        raise NotImplementedError()

    def buildDataProvider(self, page, override):
        if not self._provider_type:
            from piecrust.data.provider import get_data_provider_class
            self._provider_type = get_data_provider_class(self.app,
                                                          self.data_type)
        return self._provider_type(self, page, override)

    def finalizeConfig(self, page):
        pass

    def buildAssetor(self, page, uri):
        return Assetor(page, uri)

