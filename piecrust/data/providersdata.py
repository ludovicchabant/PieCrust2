import re
import collections.abc
from piecrust.configuration import ConfigurationError
from piecrust.dataproviders.base import (
    DataProvider, build_data_provider)


re_endpoint_sep = re.compile(r'[\/\.]')


class DataProvidersData(collections.abc.Mapping):
    def __init__(self, page):
        self._page = page
        self._dict = None

    def __getitem__(self, name):
        self._load()
        return self._dict[name]

    def __iter__(self):
        self._load()
        return iter(self._dict)

    def __len__(self):
        self._load()
        return len(self._dict)

    def _load(self):
        if self._dict is not None:
            return

        self._dict = {}
        for source in self._page.app.sources:
            pname = source.config.get('data_type') or 'page_iterator'
            pendpoint = source.config.get('data_endpoint')
            if not pname or not pendpoint:
                continue

            endpoint_bits = re_endpoint_sep.split(pendpoint)
            endpoint = self._dict
            for e in endpoint_bits[:-1]:
                if e not in endpoint:
                    endpoint[e] = {}
                endpoint = endpoint[e]
            existing = endpoint.get(endpoint_bits[-1])

            if existing is None:
                provider = build_data_provider(pname, source, self._page)
                endpoint[endpoint_bits[-1]] = provider
            elif isinstance(existing, DataProvider):
                existing_source = existing._sources[0]
                if (existing.PROVIDER_NAME != pname or
                        existing_source.SOURCE_NAME != source.SOURCE_NAME):
                    raise ConfigurationError(
                        "Can't combine data providers '%s' and '%' "
                        "(using sources '%s' and '%s') "
                        "on endpoint '%s'." %
                        (existing.PROVIDER_NAME, pname,
                         existing_source.SOURCE_NAME, source.SOURCE_NAME,
                         pendpoint))
                existing._addSource(source)
            else:
                raise ConfigurationError(
                    "Endpoint '%s' can't be used for a data provider because "
                    "it's already used for something else." % pendpoint)
