import re
import collections.abc


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
        for source in self._page.app.sources + self._page.app.generators:
            if source.data_endpoint:
                endpoint_bits = re_endpoint_sep.split(source.data_endpoint)
                endpoint = self._dict
                for e in endpoint_bits[:-1]:
                    if e not in endpoint:
                        endpoint[e] = {}
                    endpoint = endpoint[e]
                override = endpoint.get(endpoint_bits[-1])
                provider = source.buildDataProvider(self._page, override)
                if provider is not None:
                    endpoint[endpoint_bits[-1]] = provider
