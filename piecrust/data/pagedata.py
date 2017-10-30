import copy
import time
import logging
import collections.abc
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


class LazyPageConfigLoaderHasNoValue(Exception):
    """ An exception that can be returned when a loader for `LazyPageConfig`
        can't return any value.
    """
    pass


class LazyPageConfigData(collections.abc.Mapping):
    """ An object that represents the configuration header of a page,
        but also allows for additional data. It's meant to be exposed
        to the templating system.
    """
    debug_render = []
    debug_render_invoke = []
    debug_render_dynamic = ['_debugRenderKeys']
    debug_render_invoke_dynamic = ['_debugRenderKeys']

    def __init__(self, page):
        self._page = page
        self._values = {}
        self._loaders = {}
        self._is_loaded = False

    def __getattr__(self, name):
        try:
            return self._getValue(name)
        except LazyPageConfigLoaderHasNoValue as ex:
            raise AttributeError("No such attribute: %s" % name) from ex

    def __getitem__(self, name):
        try:
            return self._getValue(name)
        except LazyPageConfigLoaderHasNoValue as ex:
            raise KeyError("No such key: %s" % name) from ex

    def __iter__(self):
        keys = set(self._page.config.keys())
        keys |= set(self._values.keys())
        keys |= set(self._loaders.keys())
        keys.discard('*')
        return iter(keys)

    def __len__(self):
        return len(self._page.config) + len(self._values) + len(self._loaders)

    def _getValue(self, name):
        # First try the page configuration itself.
        try:
            return self._page.config[name]
        except KeyError:
            pass

        # Then try loaded values.
        self._ensureLoaded()
        try:
            return self._values[name]
        except KeyError:
            pass

        # Try a loader for a new value.
        loader = self._loaders.get(name)
        if loader is not None:
            try:
                with self._page.app.env.stats.timerScope('BuildLazyPageData'):
                    self._values[name] = loader(self, name)
            except (LazyPageConfigLoaderHasNoValue, AbortedSourceUseError):
                raise
            except Exception as ex:
                logger.exception(ex)
                raise Exception(
                    "Error while loading attribute '%s' for: %s" %
                    (name, self._page.content_spec)) from ex

            # Forget this loader now that it served its purpose.
            try:
                del self._loaders[name]
            except KeyError:
                pass
            return self._values[name]

        # Try the wildcard loader if it exists.
        loader = self._loaders.get('*')
        if loader is not None:
            try:
                with self._page.app.env.stats.timerScope('BuildLazyPageData'):
                    self._values[name] = loader(self, name)
            except (LazyPageConfigLoaderHasNoValue, AbortedSourceUseError):
                raise
            except Exception as ex:
                logger.exception(ex)
                raise Exception(
                    "Error while loading attribute '%s' for: %s" %
                    (name, self._page.content_spec)) from ex
            # We always keep the wildcard loader in the loaders list.
            try:
                return self._values[name]
            except KeyError:
                pass

        raise LazyPageConfigLoaderHasNoValue()

    def _setValue(self, name, value):
        self._values[name] = value

    def _unmapLoader(self, attr_name):
        try:
            del self._loaders[attr_name]
        except KeyError:
            pass

    def _mapLoader(self, attr_name, loader, override_existing=False):
        assert loader is not None

        if not override_existing and attr_name in self._loaders:
            raise Exception(
                "A loader has already been mapped for: %s" % attr_name)
        self._loaders[attr_name] = loader

    def _mapValue(self, attr_name, value, override_existing=False):
        self._mapLoader(
            attr_name,
            lambda _, __: value,
            override_existing=override_existing)

    def _ensureLoaded(self):
        if self._is_loaded:
            return

        self._is_loaded = True
        try:
            with self._page.app.env.stats.timerScope('BuildLazyPageData'):
                self._load()
        except Exception as ex:
            logger.exception(ex)
            raise Exception(
                "Error while loading data for: %s" %
                self._page.content_spec) from ex

    def _load(self):
        pass

    def _debugRenderKeys(self):
        self._ensureLoaded()
        keys = set(self._values.keys())
        if self._loaders:
            keys |= set(self._loaders.keys())
            keys.discard('*')
        return list(keys)


class PageData(LazyPageConfigData):
    """ Template data for a page.
    """
    def __init__(self, page, ctx):
        super().__init__(page)
        self._ctx = ctx

    def _load(self):
        from piecrust.uriutil import split_uri

        page = self._page
        set_val = self._setValue

        page_url = page.getUri(self._ctx.sub_num)
        _, rel_url = split_uri(page.app, page_url)

        dt = page.datetime
        for k, v in page.source_metadata.items():
            set_val(k, v)
        set_val('url', page_url)
        set_val('rel_url', rel_url)
        set_val('route', copy.deepcopy(page.source_metadata['route_params']))

        set_val('timestamp', time.mktime(dt.timetuple()))
        set_val('datetime', {
            'year': dt.year, 'month': dt.month, 'day': dt.day,
            'hour': dt.hour, 'minute': dt.minute, 'second': dt.second})

        self._mapLoader('date', _load_date)


def _load_date(data, name):
    page = data._page
    date_format = page.app.config.get('site/date_format')
    if date_format:
        return page.datetime.strftime(date_format)
    return None
