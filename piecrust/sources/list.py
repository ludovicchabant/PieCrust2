from piecrust.sources.base import ContentSource


class ListSource(ContentSource):
    def __init__(self, inner_source, items):
        super().__init__(
            inner_source.app, inner_source.name, inner_source.config)

        self.inner_source = inner_source
        self.items = items

    def openItem(self, item, mode='r', **kwargs):
        return self.inner_source.openItem(item, mode, **kwargs)

    def getItemMtime(self, item):
        return self.inner_source.getItemMtime(item)

    def getContents(self, group):
        return self.items

    def getRelatedContents(self, item, relationship):
        return self.inner_source.getRelatedContents(item, relationship)

    def findContentFromRoute(self, route_params):
        # Can't find items... we could find stuff that's not in our list?
        raise NotImplementedError(
            "The list source doesn't support finding items.")

    def getSupportedRouteParameters(self):
        return self.inner_source.getSupportedRouteParameters()

