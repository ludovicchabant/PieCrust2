import logging
import collections
from werkzeug.utils import cached_property


# Source realms, to differentiate sources in the site itself ('User')
# and sources in the site's theme ('Theme').
REALM_USER = 0
REALM_THEME = 1
REALM_NAMES = {
    REALM_USER: 'User',
    REALM_THEME: 'Theme'}


# Types of relationships a content source can be asked for.
REL_PARENT_GROUP = 1
REL_LOGICAL_PARENT_ITEM = 2
REL_LOGICAL_CHILD_GROUP = 3
REL_ASSETS = 10


logger = logging.getLogger(__name__)


class SourceNotFoundError(Exception):
    pass


class InsufficientRouteParameters(Exception):
    pass


class AbortedSourceUseError(Exception):
    pass


class GeneratedContentException(Exception):
    pass


CONTENT_TYPE_PAGE = 0
CONTENT_TYPE_ASSET = 1


class ContentItem:
    """ Describes a piece of content.

        Some known metadata that PieCrust will use include:
        - `date`: A `datetime.date` object that will set the date of the page.
        - `datetime`: A `datetime.datetime` object that will set the date and
            time of the page.
        - `route_params`: A dictionary of route parameters to generate the
            URL to the content.
        - `config`: A dictionary of configuration settings to merge into the
            settings found in the content itself.
    """
    def __init__(self, spec, metadata):
        self.spec = spec
        self.metadata = metadata

    @property
    def is_group(self):
        return False


class ContentGroup:
    """ Describes a group of `ContentItem`s.
    """
    def __init__(self, spec, metadata):
        self.spec = spec
        self.metadata = metadata

    @property
    def is_group(self):
        return True


class ContentSource:
    """ A source for content.
    """
    SOURCE_NAME = None
    DEFAULT_PIPELINE_NAME = None

    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config or {}
        self._cache = None
        self._page_cache = None

    @property
    def is_theme_source(self):
        return self.config['realm'] == REALM_THEME

    @cached_property
    def route(self):
        return self.app.getSourceRoute(self.name)

    def openItem(self, item, mode='r', **kwargs):
        raise NotImplementedError()

    def getItemMtime(self, item):
        raise NotImplementedError()

    def getAllPages(self):
        if self._page_cache is not None:
            return self._page_cache

        getter = self.app.getPage
        self._page_cache = [getter(self, i) for i in self.getAllContents()]
        return self._page_cache

    def getAllContents(self):
        if self._cache is not None:
            return self._cache

        cache = []
        stack = collections.deque()
        stack.append(None)
        while len(stack) > 0:
            cur = stack.popleft()
            try:
                contents = self.getContents(cur)
            except GeneratedContentException:
                continue
            if contents is not None:
                for c in contents:
                    if c.is_group:
                        stack.append(c)
                    else:
                        cache.append(c)
        self._cache = cache
        return cache

    def getContents(self, group):
        raise NotImplementedError(
            "'%s' doesn't implement 'getContents'." % self.__class__)

    def getRelatedContents(self, item, relationship):
        raise NotImplementedError(
            "'%s' doesn't implement 'getRelatedContents'." % self.__class__)

    def findContentFromSpec(self, spec):
        raise NotImplementedError(
            "'%s' doesn't implement 'findContentFromSpec'." % self.__class__)

    def findContentFromRoute(self, route_params):
        raise NotImplementedError(
            "'%s' doesn't implement 'findContentFromRoute'." % self.__class__)

    def getSupportedRouteParameters(self):
        raise NotImplementedError(
            "'%s' doesn't implement 'getSupportedRouteParameters'." %
            self.__class__)

    def prepareRenderContext(self, ctx):
        pass

    def onRouteFunctionUsed(self, route_params):
        pass

    def describe(self):
        return None

