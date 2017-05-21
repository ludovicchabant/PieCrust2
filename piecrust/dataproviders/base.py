from piecrust.configuration import ConfigurationError


class UnsupportedWrappedDataProviderError(Exception):
    pass


class DataProvider:
    """ The base class for a data provider.
    """
    PROVIDER_NAME = None

    debug_render_dynamic = []
    debug_render_invoke_dynamic = []

    def __init__(self, source):
        self._source = source

    def _wrapDataProvider(self, provider):
        raise UnsupportedWrappedDataProviderError()


def get_data_provider_class(app, provider_type):
    if not provider_type:
        raise Exception("No data provider type specified.")
    for prov in app.plugin_loader.getDataProviders():
        if prov.PROVIDER_NAME == provider_type:
            return prov
    raise ConfigurationError(
        "Unknown data provider type: %s" % provider_type)

