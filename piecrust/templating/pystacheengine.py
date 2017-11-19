import logging
import collections.abc
from piecrust.templating.base import (
    TemplateEngine, TemplateNotFoundError, TemplatingError)


logger = logging.getLogger(__name__)


class PystacheTemplateEngine(TemplateEngine):
    ENGINE_NAMES = ['mustache']
    EXTENSIONS = ['mustache']

    def __init__(self):
        self.renderer = None
        self._not_found_error = None
        self._pystache_error = None

    def renderSegment(self, path, segment, data):
        self._ensureLoaded()
        try:
            return self.renderer.render(segment.content, data), True
        except self._not_found_error as ex:
            raise TemplateNotFoundError() from ex
        except self._pystache_error as ex:
            raise TemplatingError(str(ex), path) from ex

    def renderFile(self, paths, data):
        self._ensureLoaded()
        tpl = None
        logger.debug("Looking for template: %s" % paths)
        for p in paths:
            if not p.endswith('.mustache'):
                raise TemplatingError(
                    "The Mustache template engine only accepts template "
                    "filenames with a `.mustache` extension. Got: %s" %
                    p)
            name = p[:-9]  # strip `.mustache`
            try:
                tpl = self.renderer.load_template(name)
            except Exception as ex:
                logger.debug("Mustache error: %s" % ex)
                pass

        if tpl is None:
            raise TemplateNotFoundError()

        try:
            return self.renderer.render(tpl, data)
        except self._pystache_error as ex:
            raise TemplatingError(str(ex)) from ex

    def _ensureLoaded(self):
        if self.renderer:
            return

        import pystache
        import pystache.common

        self._not_found_error = pystache.common.TemplateNotFoundError
        self._pystache_error = pystache.common.PystacheError

        class _WorkaroundRenderer(pystache.Renderer):
            def _make_resolve_context(self):
                mrc = super(_WorkaroundRenderer, self)._make_resolve_context()

                def _workaround(stack, name):
                    # Pystache will treat anything that's not a string or
                    # a dict as a list. This is just plain wrong, but it will
                    # take a while before the project can get patches on Pypi.
                    res = mrc(stack, name)
                    if res is not None and (
                            res.__class__.__name__ in _knowns or
                            isinstance(res, collections.abc.Mapping)):
                        res = [res]
                    return res

                return _workaround

        self.renderer = _WorkaroundRenderer(
            search_dirs=self.app.templates_dirs)


_knowns = ['PieCrustData', 'LazyPageConfigData', 'Paginator', 'Assetor',
           'PageLinkerData']
