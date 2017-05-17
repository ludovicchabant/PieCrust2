import logging
import collections


# Source realms, to differentiate sources in the site itself ('User')
# and sources in the site's theme ('Theme').
REALM_USER = 0
REALM_THEME = 1
REALM_NAMES = {
    REALM_USER: 'User',
    REALM_THEME: 'Theme'}


# Types of relationships a content source can be asked for.
REL_ASSETS = 1


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
    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config or {}

    @property
    def is_theme_source(self):
        return self.config['realm'] == REALM_THEME

    @property
    def root_dir(self):
        if self.is_theme_source:
            return self.app.theme_dir
        return self.app.root_dir

    def openItem(self, item, mode='r'):
        raise NotImplementedError()

    def getItemMtime(self, item):
        raise NotImplementedError()

    def getAllContents(self):
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
                        yield c

    def getContents(self, group):
        raise NotImplementedError("'%s' doesn't implement 'getContents'." %
                                  self.__class__)

    def getRelatedContents(self, item, relationship):
        raise NotImplementedError()

    def findContent(self, route_params):
        raise NotImplementedError()

    def getSupportedRouteParameters(self):
        raise NotImplementedError()

    def prepareRenderContext(self, ctx):
        pass

    def onRouteFunctionUsed(self, route_params):
        pass

    def describe(self):
        return None

