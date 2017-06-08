from piecrust.configuration import ConfigurationError


class DataProvider:
    """ The base class for a data provider.
    """
    PROVIDER_NAME = None

    debug_render_dynamic = []
    debug_render_invoke_dynamic = []

    def __init__(self, source, page):
        self._sources = [source]
        self._page = page
        self._app = source.app

    def _addSource(self, source):
        self._sources.append(source)


def build_data_provider(provider_type, source, page):
    if not provider_type:
        raise Exception("No data provider type specified.")

    for p in page.app.plugin_loader.getDataProviders():
        if p.PROVIDER_NAME == provider_type:
            pclass = p
            break
    else:
        raise ConfigurationError("Unknown data provider type: %s" %
                                 provider_type)

    return pclass(source, page)

