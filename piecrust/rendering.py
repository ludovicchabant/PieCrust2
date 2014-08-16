import re
import os.path
import logging
from piecrust.data.builder import (DataBuildingContext, build_page_data,
        build_layout_data)
from piecrust.environment import PHASE_PAGE_FORMATTING, PHASE_PAGE_RENDERING


logger = logging.getLogger(__name__)


content_abstract_re = re.compile(r'^<!--\s*(more|(page)?break)\s*-->\s*$',
                                 re.MULTILINE)


class PageRenderingError(Exception):
    pass


class RenderedPage(object):
    def __init__(self, page, uri, num=1):
        self.page = page
        self.uri = uri
        self.num = num
        self.data = None
        self.content = None
        self.execution_info = None

    @property
    def app(self):
        return self.page.app


class PageRenderingContext(object):
    def __init__(self, page, uri, page_num=1):
        self.page = page
        self.uri = uri
        self.page_num = page_num
        self.pagination_source = None
        self.pagination_filter = None
        self.custom_data = None
        self.use_cache = False
        self.used_pagination = None
        self.used_source_names = set()
        self.used_taxonomy_terms = set()

    @property
    def app(self):
        return self.page.app

    @property
    def source_metadata(self):
        return self.page.source_metadata

    def reset(self):
        self.used_pagination = None

    def setPagination(self, paginator):
        if self.used_pagination is not None:
            raise Exception("Pagination has already been used.")
        self.used_pagination = paginator


def render_page(ctx):
    eis = ctx.app.env.exec_info_stack
    eis.pushPage(ctx.page, PHASE_PAGE_RENDERING, ctx)
    try:
        page = ctx.page

        # Build the data for both segment and layout rendering.
        data_ctx = DataBuildingContext(page, ctx.uri, ctx.page_num)
        data_ctx.pagination_source = ctx.pagination_source
        data_ctx.pagination_filter = ctx.pagination_filter
        page_data = build_page_data(data_ctx)
        if ctx.custom_data:
            page_data.update(ctx.custom_data)

        # Render content segments.
        repo = ctx.app.env.rendered_segments_repository
        if repo:
            cache_key = '%s:%s' % (ctx.uri, ctx.page_num)
            contents = repo.get(cache_key,
                    lambda: _do_render_page_segments(page, page_data))
        else:
            contents = _do_render_page_segments(page, page_data)

        # Render layout.
        layout_name = page.config.get('layout')
        if layout_name is None:
            layout_name = page.source.config.get('default_layout', 'default')
        null_names = ['', 'none', 'nil']
        if layout_name not in null_names:
            layout_data = build_layout_data(page, page_data, contents)
            output = render_layout(layout_name, page, layout_data)
        else:
            output = contents['content']

        rp = RenderedPage(page, ctx.uri, ctx.page_num)
        rp.data = page_data
        rp.content = output
        rp.execution_info = eis.current_page_info
        return rp
    finally:
        eis.popPage()


def render_page_segments(ctx):
    repo = ctx.app.env.rendered_segments_repository
    if repo:
        cache_key = '%s:%s' % (ctx.uri, ctx.page_num)
        return repo.get(cache_key,
            lambda: _do_render_page_segments_from_ctx(ctx))

    return _do_render_page_segments_from_ctx(ctx)


def _do_render_page_segments_from_ctx(ctx):
    eis = ctx.app.env.exec_info_stack
    eis.pushPage(ctx.page, PHASE_PAGE_FORMATTING, ctx)
    try:
        data_ctx = DataBuildingContext(ctx.page, ctx.uri, ctx.page_num)
        page_data = build_page_data(data_ctx)
        return _do_render_page_segments(ctx.page, page_data)
    finally:
        eis.popPage()


def _do_render_page_segments(page, page_data):
    app = page.app
    engine_name = page.config.get('template_engine')
    format_name = page.config.get('format')

    engine = get_template_engine(app, engine_name)
    if engine is None:
        raise PageRenderingError("Can't find template engine '%s'." % engine_name)

    formatted_content = {}
    for seg_name, seg in page.raw_content.items():
        seg_text = ''
        for seg_part in seg.parts:
            part_format = seg_part.fmt or format_name
            part_text = engine.renderString(seg_part.content, page_data,
                    filename=page.path, line_offset=seg_part.line)
            part_text = format_text(app, part_format, part_text)
            seg_text += part_text
        formatted_content[seg_name] = seg_text

        if seg_name == 'content':
            m = content_abstract_re.search(seg_text)
            if m:
                offset = m.start()
                content_abstract = seg_text[:offset]
                formatted_content['content.abstract'] = content_abstract

    return formatted_content


def render_layout(layout_name, page, layout_data):
    names = layout_name.split(',')
    default_template_engine = get_template_engine(page.app, None)
    default_exts = ['.' + e.lstrip('.') for e in default_template_engine.EXTENSIONS]
    full_names = []
    for name in names:
        if '.' not in name:
            full_names.append(name + '.html')
            for ext in default_exts:
                full_names.append(name + ext)
        else:
            full_names.append(name)

    _, engine_name = os.path.splitext(full_names[0])
    engine_name = engine_name.lstrip('.')
    engine = get_template_engine(page.app, engine_name)
    if engine is None:
        raise PageRenderingError("No such template engine: %s" % engine_name)
    output = engine.renderFile(full_names, layout_data)
    return output


def get_template_engine(app, engine_name):
    if engine_name == 'html':
        engine_name = None
    engine_name = engine_name or app.config.get('site/default_template_engine')
    for engine in app.plugin_loader.getTemplateEngines():
        if engine_name in engine.ENGINE_NAMES:
            return engine
    return None

def format_text(app, format_name, txt):
    format_name = format_name or app.config.get('site/default_format')
    for fmt in app.plugin_loader.getFormatters():
        if fmt.FORMAT_NAMES is None or format_name in fmt.FORMAT_NAMES:
            txt = fmt.render(format_name, txt)
            if fmt.OUTPUT_FORMAT is not None:
                format_name = fmt.OUTPUT_FORMAT
    return txt

