

class IPaginationSource(object):
    """ Defines the interface for a source that can be used as the data
        for an iterator or a pagination.
    """
    def getItemsPerPage(self):
        raise NotImplementedError()

    def getSourceIterator(self):
        raise NotImplementedError()

    def getSorterIterator(self, it):
        raise NotImplementedError()

    def getTailIterator(self, it):
        raise NotImplementedError()

    def getPaginationFilter(self, page):
        raise NotImplementedError()

    def getSettingAccessor(self):
        raise NotImplementedError()


class IListableSource(object):
    """ Defines the interface for a source that can be iterated on in a
        hierarchical manner, for use with the `family` data endpoint.
    """
    def listPath(self, rel_path):
        raise NotImplementedError()

    def getDirpath(self, rel_path):
        raise NotImplementedError()

    def getBasename(self, rel_path):
        raise NotImplementedError()


class IPreparingSource(object):
    """ Defines the interface for a source whose pages can be created by the
        `chef prepare` command.
    """
    def setupPrepareParser(self, parser, app):
        raise NotImplementedError()

    def buildMetadata(self, args):
        raise NotImplementedError()


class InteractiveField(object):
    TYPE_STRING = 0
    TYPE_INT = 1

    def __init__(self, name, field_type, default_value):
        self.name = name
        self.field_type = field_type
        self.default_value = default_value


class IInteractiveSource(object):
    def getInteractiveFields(self):
        raise NotImplementedError()

