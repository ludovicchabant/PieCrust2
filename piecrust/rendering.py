import re
import os.path
import copy
import logging
from piecrust.data.builder import (
    DataBuildingContext, build_page_data, add_layout_data)
from piecrust.templating.base import TemplateNotFoundError, TemplatingError
from piecrust.sources.base import AbortedSourceUseError


logger = logging.getLogger(__name__)


content_abstract_re = re.compile(r'^<!--\s*(more|(page)?break)\s*-->\s*$',
                                 re.MULTILINE)


class RenderingError(Exception):
    pass


class TemplateEngineNotFound(Exception):
    pass


class RenderedSegments(object):
    def __init__(self, segments, render_pass_info):
        self.segments = segments
        self.render_pass_info = render_pass_info


class RenderedLayout(object):
    def __init__(self, content, render_pass_info):
        self.content = content
        self.render_pass_info = render_pass_info


class RenderedPage(object):
    def __init__(self, page, sub_num):
        self.page = page
        self.sub_num = sub_num
        self.data = None
        self.content = None
        self.render_info = [None, None]

    @property
    def app(self):
        return self.page.app

    def copyRenderInfo(self):
        return copy.deepcopy(self.render_info)


PASS_NONE = -1
PASS_FORMATTING = 0
PASS_RENDERING = 1


RENDER_PASSES = [PASS_FORMATTING, PASS_RENDERING]


class RenderPassInfo(object):
    def __init__(self):
        self.used_source_names = set()
        self.used_pagination = False
        self.pagination_has_more = False
        self.used_assets = False
        self._custom_info = {}

    def setCustomInfo(self, key, info):
        self._custom_info[key] = info

    def getCustomInfo(self, key, default=None, create_if_missing=False):
        if create_if_missing:
            return self._custom_info.setdefault(key, default)
        return self._custom_info.get(key, default)


class RenderingContext(object):
    def __init__(self, page, *, sub_num=1, force_render=False):
        self.page = page
        self.sub_num = sub_num
        self.force_render = force_render
        self.pagination_source = None
        self.pagination_filter = None
        self.custom_data = {}
        self.render_passes = [None, None]  # Same length as RENDER_PASSES
        self._current_pass = PASS_NONE

    @property
    def app(self):
        return self.page.app

    @property
    def current_pass_info(self):
        if self._current_pass != PASS_NONE:
            return self.render_passes[self._current_pass]
        return None

    def setCurrentPass(self, rdr_pass):
        if rdr_pass != PASS_NONE:
            self.render_passes[rdr_pass] = RenderPassInfo()
        self._current_pass = rdr_pass

    def setPagination(self, paginator):
        self._raiseIfNoCurrentPass()
        pass_info = self.current_pass_info
        if pass_info.used_pagination:
            raise Exception("Pagination has already been used.")
        assert paginator.is_loaded
        pass_info.used_pagination = True
        pass_info.pagination_has_more = paginator.has_more
        self.addUsedSource(paginator._source)

    def addUsedSource(self, source):
        self._raiseIfNoCurrentPass()
        pass_info = self.current_pass_info
        pass_info.used_source_names.add(source.name)

    def _raiseIfNoCurrentPass(self):
        if self._current_pass == PASS_NONE:
            raise Exception("No rendering pass is currently active.")


class RenderingContextStack(object):
    def __init__(self):
        self._ctx_stack = []

    @property
    def is_empty(self):
        return len(self._ctx_stack) == 0

    @property
    def current_ctx(self):
        if len(self._ctx_stack) == 0:
            return None
        return self._ctx_stack[-1]

    @property
    def is_main_ctx(self):
        return len(self._ctx_stack) == 1

    def hasPage(self, page):
        for ei in self._ctx_stack:
            if ei.page == page:
                return True
        return False

    def pushCtx(self, render_ctx):
        for ctx in self._ctx_stack:
            if ctx.page == render_ctx.page:
                raise Exception("Loop detected during rendering!")
        self._ctx_stack.append(render_ctx)

    def popCtx(self):
        del self._ctx_stack[-1]

    def clear(self):
        self._ctx_stack = []


def render_page(ctx):
    env = ctx.app.env
    stats = env.stats

    stack = env.render_ctx_stack
    stack.pushCtx(ctx)

    page = ctx.page
    page_uri = page.getUri(ctx.sub_num)

    try:
        # Build the data for both segment and layout rendering.
        with stats.timerScope("BuildRenderData"):
            page_data = _build_render_data(ctx)

        # Render content segments.
        ctx.setCurrentPass(PASS_FORMATTING)
        repo = env.rendered_segments_repository
        save_to_fs = True
        if env.fs_cache_only_for_main_page and not stack.is_main_ctx:
            save_to_fs = False
        with stats.timerScope("PageRenderSegments"):
            if repo is not None and not ctx.force_render:
                render_result = repo.get(
                    page_uri,
                    lambda: _do_render_page_segments(ctx, page_data),
                    fs_cache_time=page.content_mtime,
                    save_to_fs=save_to_fs)
            else:
                render_result = _do_render_page_segments(ctx, page_data)
                if repo:
                    repo.put(page_uri, render_result, save_to_fs)

        # Render layout.
        ctx.setCurrentPass(PASS_RENDERING)
        layout_name = page.config.get('layout')
        if layout_name is None:
            layout_name = page.source.config.get(
                'default_layout', 'default')
        null_names = ['', 'none', 'nil']
        if layout_name not in null_names:
            with stats.timerScope("BuildRenderData"):
                add_layout_data(page_data, render_result.segments)

            with stats.timerScope("PageRenderLayout"):
                layout_result = _do_render_layout(
                    layout_name, page, page_data)
        else:
            layout_result = RenderedLayout(
                render_result.segments['content'], None)

        rp = RenderedPage(page, ctx.sub_num)
        rp.data = page_data
        rp.content = layout_result.content
        rp.render_info[PASS_FORMATTING] = render_result.render_pass_info
        rp.render_info[PASS_RENDERING] = layout_result.render_pass_info
        return rp

    except AbortedSourceUseError:
        raise
    except Exception as ex:
        if ctx.app.debug:
            raise
        logger.exception(ex)
        raise Exception("Error rendering page: %s" %
                        ctx.page.content_spec) from ex

    finally:
        ctx.setCurrentPass(PASS_NONE)
        stack.popCtx()


def render_page_segments(ctx):
    env = ctx.app.env
    stats = env.stats

    stack = env.render_ctx_stack

    if env.abort_source_use and not stack.is_empty:
        cur_spec = ctx.page.content_spec
        from_spec = stack.current_ctx.page.content_spec
        logger.debug("Aborting rendering of '%s' from: %s." %
                     (cur_spec, from_spec))
        raise AbortedSourceUseError()

    stack.pushCtx(ctx)

    page = ctx.page
    page_uri = page.getUri(ctx.sub_num)

    try:
        ctx.setCurrentPass(PASS_FORMATTING)
        repo = env.rendered_segments_repository

        save_to_fs = True
        if env.fs_cache_only_for_main_page and not stack.is_main_ctx:
            save_to_fs = False

        with stats.timerScope("PageRenderSegments"):
            if repo is not None and not ctx.force_render:
                render_result = repo.get(
                    page_uri,
                    lambda: _do_render_page_segments_from_ctx(ctx),
                    fs_cache_time=page.content_mtime,
                    save_to_fs=save_to_fs)
            else:
                render_result = _do_render_page_segments_from_ctx(ctx)
                if repo:
                    repo.put(page_uri, render_result, save_to_fs)
    finally:
        ctx.setCurrentPass(PASS_NONE)
        stack.popCtx()

    return render_result


def _build_render_data(ctx):
    data_ctx = DataBuildingContext(ctx.page, ctx.sub_num)
    data_ctx.pagination_source = ctx.pagination_source
    data_ctx.pagination_filter = ctx.pagination_filter
    page_data = build_page_data(data_ctx)
    if ctx.custom_data:
        page_data._appendMapping(ctx.custom_data)
    return page_data


def _do_render_page_segments_from_ctx(ctx):
    page_data = _build_render_data(ctx)
    return _do_render_page_segments(ctx, page_data)


def _do_render_page_segments(ctx, page_data):
    page = ctx.page
    app = page.app

    engine_name = page.config.get('template_engine')
    format_name = page.config.get('format')

    engine = get_template_engine(app, engine_name)

    formatted_segments = {}
    for seg_name, seg in page.segments.items():
        try:
            with app.env.stats.timerScope(
                    engine.__class__.__name__ + '_segment'):
                seg_text = engine.renderSegment(
                    page.content_spec, seg, page_data)
        except TemplatingError as err:
            err.lineno += seg.line
            raise err

        seg_format = seg.fmt or format_name
        seg_text = format_text(app, seg_format, seg_text)
        formatted_segments[seg_name] = seg_text

        if seg_name == 'content':
            m = content_abstract_re.search(seg_text)
            if m:
                offset = m.start()
                content_abstract = seg_text[:offset]
                formatted_segments['content.abstract'] = content_abstract

    pass_info = ctx.render_passes[PASS_FORMATTING]
    res = RenderedSegments(formatted_segments, pass_info)

    app.env.stats.stepCounter('PageRenderSegments')

    return res


def _do_render_layout(layout_name, page, layout_data):
    app = page.app
    cur_ctx = app.env.render_ctx_stack.current_ctx
    assert cur_ctx is not None
    assert cur_ctx.page == page

    names = layout_name.split(',')
    full_names = []
    for name in names:
        if '.' not in name:
            full_names.append(name + '.html')
        else:
            full_names.append(name)

    _, engine_name = os.path.splitext(full_names[0])
    engine_name = engine_name.lstrip('.')
    engine = get_template_engine(app, engine_name)

    try:
        with app.env.stats.timerScope(
                engine.__class__.__name__ + '_layout'):
            output = engine.renderFile(full_names, layout_data)
    except TemplateNotFoundError as ex:
        logger.exception(ex)
        msg = "Can't find template for page: %s\n" % page.content_item.spec
        msg += "Looked for: %s" % ', '.join(full_names)
        raise Exception(msg) from ex

    pass_info = cur_ctx.render_passes[PASS_RENDERING]
    res = RenderedLayout(output, pass_info)

    app.env.stats.stepCounter('PageRenderLayout')

    return res


def get_template_engine(app, engine_name):
    if engine_name == 'html':
        engine_name = None
    engine_name = engine_name or app.config.get('site/default_template_engine')
    for engine in app.plugin_loader.getTemplateEngines():
        if engine_name in engine.ENGINE_NAMES:
            return engine
    raise TemplateEngineNotFound("No such template engine: %s" % engine_name)


def format_text(app, format_name, txt, exact_format=False):
    if exact_format and not format_name:
        raise Exception("You need to specify a format name.")

    format_count = 0
    format_name = format_name or app.config.get('site/default_format')

    auto_fmts = app.config.get('site/auto_formats')
    redirect = auto_fmts.get(format_name)
    if redirect is not None:
        format_name = redirect

    for fmt in app.plugin_loader.getFormatters():
        if not fmt.enabled:
            continue
        if fmt.FORMAT_NAMES is None or format_name in fmt.FORMAT_NAMES:
            with app.env.stats.timerScope(fmt.__class__.__name__):
                txt = fmt.render(format_name, txt)
            format_count += 1
            if fmt.OUTPUT_FORMAT is not None:
                format_name = fmt.OUTPUT_FORMAT
    if exact_format and format_count == 0:
        raise Exception("No such format: %s" % format_name)
    return txt

