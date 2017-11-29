import io
import os.path
import time
import logging
from inukshuk.parser import ParserError
from piecrust.templating.base import (
    TemplateEngine, TemplatingError, TemplateNotFoundError)


logger = logging.getLogger(__name__)

_profile = False


class InukshukTemplateEngine(TemplateEngine):
    ENGINE_NAMES = ['inukshuk', 'inuk']
    EXTENSIONS = ['html', 'inuk']

    def __init__(self):
        self.engine = None
        self.pc_cache = {}
        self._seg_loader = None
        self._buf = io.StringIO()
        self._buf.truncate(2048)
        if _profile:
            self._renderTemplate = self._renderTemplateProf
        else:
            self._renderTemplate = self._renderTemplateNoProf

    def populateCache(self):
        self._ensureLoaded()

        used_names = set()

        def _filter_names(name):
            if name in used_names:
                return False
            used_names.add(name)
            return True

        self.engine.cacheAllTemplates(cache_condition=_filter_names)

    def renderSegment(self, path, segment, data):
        if not _string_needs_render(segment.content):
            return segment.content, False

        self._ensureLoaded()

        tpl_name = os.path.relpath(path, self.app.root_dir)
        try:
            self._seg_loader.templates[tpl_name] = segment.content
            tpl = self.engine.getTemplate(tpl_name, memmodule=True)
            return self._renderTemplate(tpl, data), True
        except ParserError as pe:
            raise TemplatingError(pe.message, path, pe.line_num)

    def renderFile(self, paths, data):
        self._ensureLoaded()

        tpl = None
        rendered_path = None
        for p in paths:
            try:
                tpl = self.engine.getTemplate(p)
                rendered_path = p
                break
            except Exception:
                pass

        if tpl is None:
            raise TemplateNotFoundError()

        try:
            return self._renderTemplate(tpl, data)
        except ParserError as pe:
            raise TemplatingError(pe.message, rendered_path, pe.line_num)

    def _renderTemplateNoProf(self, tpl, data):
        return tpl.render(data)

    def _renderTemplateIntoNoProf(self, tpl, data):
        buf = self._buf
        buf.seek(0)
        tpl.renderInto(data, buf)
        buf.flush()
        size = buf.tell()
        buf.seek(0)
        return buf.read(size)

    def _renderTemplateProf(self, tpl, data):
        stats = self.app.env.stats

        # Code copied from Inukshuk, but with an `out_write` method that
        # wraps a timer scope.
        out = []

        def out_write(s):
            start = time.perf_counter()
            out.append(s)
            stats.stepTimerSince('Inukshuk_outWrite', start)

        tpl._renderWithContext(None, data, out_write)
        return ''.join(out)

    def _ensureLoaded(self):
        if self.engine is not None:
            return

        from inukshuk.engine import Engine
        from inukshuk.loader import (
            StringsLoader, FileSystemLoader, CompositeLoader)
        from ._inukshukext import PieCrustExtension

        self._seg_loader = StringsLoader()
        loader = CompositeLoader([
            self._seg_loader,
            FileSystemLoader(self.app.templates_dirs)])
        self.engine = Engine(loader)
        self.engine.autoescape = True
        self.engine.extensions.append(PieCrustExtension(self.app))
        self.engine.compile_templates = True
        self.engine.compile_cache_dir = os.path.join(
            self.app.cache_dir, 'inuk')

        if _profile:
            # If we're profiling, monkeypatch all the appropriate methods
            # from the Inukshuk API.
            stats = self.app.env.stats

            import inukshuk.rendering

            afe = inukshuk.rendering._attr_first_access

            def wafe(ctx, data, prop_name):
                with stats.timerScope('Inukshuk_query'):
                    return afe(ctx, data, prop_name)

            inukshuk.rendering._attr_first_access = wafe

            afer = inukshuk.rendering._attr_first_access_root

            def wafer(ctx, ctx_locals, data, ctx_globals, prop_name):
                with stats.timerScope('Inukshuk_query'):
                    return afer(ctx, ctx_locals, data, ctx_globals, prop_name)

            inukshuk.rendering._attr_first_access_root = wafer

            i = inukshuk.rendering.RenderContext.invoke

            def wi(ctx, data, out, data_func, *args, **kwargs):
                with stats.timerScope('Inukshuk_invoke'):
                    return i(ctx, data, out, data_func, *args, **kwargs)

            inukshuk.rendering.RenderContext.invoke = wi

            import inukshuk.template

            cc = inukshuk.template.Template._compileContent

            def wcc(tpl, force_compiled=False):
                with stats.timerScope('Inukshuk_templateCompileContent'):
                    return cc(tpl, force_compiled)

            inukshuk.template.Template._compileContent = wcc

            dr = inukshuk.template.Template._doRender

            def wdr(tpl, ctx, data, out):
                with stats.timerScope('Inukshuk_templateDoRender'):
                    return dr(tpl, ctx, data, out)

            inukshuk.template.Template._doRender = wdr

            stats.registerTimer('Inukshuk_query')
            stats.registerTimer('Inukshuk_invoke')
            stats.registerTimer('Inukshuk_templateDoRender')
            stats.registerTimer('Inukshuk_templateCompileContent')
            stats.registerTimer('Inukshuk_outWrite')

        try:
            os.makedirs(self.engine.compile_cache_dir)
        except OSError:
            pass


def _string_needs_render(txt):
    index = txt.find('{')
    while index >= 0:
        ch = txt[index + 1]
        if ch == '{' or ch == '%':
            return True
        index = txt.find('{', index + 1)
    return False
