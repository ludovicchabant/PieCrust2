import logging
import collections.abc
import pystache
import pystache.common
from piecrust.templating.base import (
        TemplateEngine, TemplateNotFoundError, TemplatingError)


logger = logging.getLogger(__name__)


class PystacheTemplateEngine(TemplateEngine):
    ENGINE_NAMES = ['mustache']
    EXTENSIONS = ['mustache']

    def __init__(self):
        self.renderer = None

    def renderString(self, txt, data, filename=None):
        self._ensureLoaded()
        try:
            return self.renderer.render(txt, data)
        except pystache.common.TemplateNotFoundError as ex:
            raise TemplateNotFoundError() from ex
        except pystache.common.PystacheError as ex:
            raise TemplatingError(str(ex), filename) from ex

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
                print(p, ex)
                pass

        if tpl is None:
            raise TemplateNotFoundError()

        try:
            return self.renderer.render(tpl, data)
        except pystache.common.PystacheError as ex:
            raise TemplatingError(str(ex)) from ex

    def _ensureLoaded(self):
        if self.renderer:
            return

        self.renderer = _WorkaroundRenderer(
                search_dirs=self.app.templates_dirs)


_knowns = ['PieCrustData', 'LazyPageConfigData', 'Paginator', 'Assetor',
           'PageLinkerData']


class _WorkaroundRenderer(pystache.Renderer):
    def _make_resolve_context(self):
        mrc = super(_WorkaroundRenderer, self)._make_resolve_context()

        def _workaround(stack, name):
            # Pystache will treat anything that's not a string or a dict as
            # a list. This is just plain wrong, but it will take a while before
            # the project can get patches on Pypi.
            res = mrc(stack, name)
            if res is not None and (
                    res.__class__.__name__ in _knowns or
                    isinstance(res, collections.abc.Mapping)):
                res = [res]
            return res

        return _workaround

