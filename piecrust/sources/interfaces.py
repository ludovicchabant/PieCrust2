

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

    def getSettingAccessor(self):
        raise NotImplementedError()


class IPreparingSource(object):
    """ Defines the interface for a source whose pages can be created by the
        `chef prepare` command.
    """
    def setupPrepareParser(self, parser, app):
        raise NotImplementedError()

    def createContent(self, args):
        raise NotImplementedError()


class InteractiveField(object):
    """ A field to display in the administration web UI.
    """
    TYPE_STRING = 0
    TYPE_INT = 1

    def __init__(self, name, field_type, default_value):
        self.name = name
        self.field_type = field_type
        self.default_value = default_value


class IInteractiveSource(object):
    """ A content source that a user can interact with in the administration
        web UI.
    """
    def getInteractiveFields(self):
        raise NotImplementedError()

