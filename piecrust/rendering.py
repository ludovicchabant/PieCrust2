import re
import os.path
import logging
from werkzeug.utils import cached_property
from piecrust.data.builder import (DataBuildingContext, build_page_data,
        build_layout_data)
from piecrust.data.filters import (
        PaginationFilter, HasFilterClause, IsFilterClause, AndBooleanClause,
        page_value_accessor)
from piecrust.sources.base import PageSource
from piecrust.templating.base import TemplateNotFoundError, TemplatingError


logger = logging.getLogger(__name__)


content_abstract_re = re.compile(r'^<!--\s*(more|(page)?break)\s*-->\s*$',
                                 re.MULTILINE)


class PageRenderingError(Exception):
    pass


class TemplateEngineNotFound(Exception):
    pass


class QualifiedPage(object):
    def __init__(self, page, route, route_metadata):
        self.page = page
        self.route = route
        self.route_metadata = route_metadata

    def getUri(self, sub_num=1):
        return self.route.getUri(self.route_metadata, provider=self.page,
                                 sub_num=sub_num)

    def __getattr__(self, name):
        return getattr(self.page, name)


class RenderedPage(object):
    def __init__(self, page, uri, num=1):
        self.page = page
        self.uri = uri
        self.num = num
        self.data = None
        self.content = None

    @property
    def app(self):
        return self.page.app


PASS_NONE = 0
PASS_FORMATTING = 1
PASS_RENDERING = 2


RENDER_PASSES = [PASS_FORMATTING, PASS_RENDERING]


class RenderPassInfo(object):
    def __init__(self):
        self.used_source_names = set()
        self.used_taxonomy_terms = set()


class PageRenderingContext(object):
    def __init__(self, qualified_page, page_num=1, force_render=False):
        self.page = qualified_page
        self.page_num = page_num
        self.force_render = force_render
        self.pagination_source = None
        self.pagination_filter = None
        self.custom_data = None
        self._current_pass = PASS_NONE

        self.render_passes = {}
        self.used_pagination = None
        self.used_assets = None

    @property
    def app(self):
        return self.page.app

    @property
    def source_metadata(self):
        return self.page.source_metadata

    @cached_property
    def uri(self):
        return self.page.getUri(self.page_num)

    @property
    def current_pass_info(self):
        return self.render_passes.get(self._current_pass)

    def setCurrentPass(self, rdr_pass):
        if rdr_pass != PASS_NONE:
            self.render_passes.setdefault(rdr_pass, RenderPassInfo())
        self._current_pass = rdr_pass

    def setPagination(self, paginator):
        self._raiseIfNoCurrentPass()
        if self.used_pagination is not None:
            raise Exception("Pagination has already been used.")
        self.used_pagination = paginator
        self.addUsedSource(paginator._source)

    def addUsedSource(self, source):
        self._raiseIfNoCurrentPass()
        if isinstance(source, PageSource):
            pass_info = self.render_passes[self._current_pass]
            pass_info.used_source_names.add(source.name)

    def setTaxonomyFilter(self, taxonomy, term_value):
        is_combination = isinstance(term_value, tuple)
        flt = PaginationFilter(value_accessor=page_value_accessor)
        if taxonomy.is_multiple:
            if is_combination:
                abc = AndBooleanClause()
                for t in term_value:
                    abc.addClause(HasFilterClause(taxonomy.setting_name, t))
                flt.addClause(abc)
            else:
                flt.addClause(
                        HasFilterClause(taxonomy.setting_name, term_value))
        else:
            flt.addClause(IsFilterClause(taxonomy.setting_name, term_value))
        self.pagination_filter = flt

        self.custom_data = {
                taxonomy.term_name: term_value,
                'is_multiple_%s' % taxonomy.term_name: is_combination}

    def _raiseIfNoCurrentPass(self):
        if self._current_pass == PASS_NONE:
            raise Exception("No rendering pass is currently active.")


def render_page(ctx):
    eis = ctx.app.env.exec_info_stack
    eis.pushPage(ctx.page, ctx)
    try:
        page = ctx.page

        # Build the data for both segment and layout rendering.
        data_ctx = DataBuildingContext(page, page_num=ctx.page_num)
        data_ctx.pagination_source = ctx.pagination_source
        data_ctx.pagination_filter = ctx.pagination_filter
        page_data = build_page_data(data_ctx)
        if ctx.custom_data:
            page_data.update(ctx.custom_data)

        # Render content segments.
        ctx.setCurrentPass(PASS_FORMATTING)
        repo = ctx.app.env.rendered_segments_repository
        if repo and not ctx.force_render:
            cache_key = ctx.uri
            page_time = page.path_mtime
            contents = repo.get(
                    cache_key,
                    lambda: _do_render_page_segments(page, page_data),
                    fs_cache_time=page_time)
        else:
            contents = _do_render_page_segments(page, page_data)

        # Render layout.
        ctx.setCurrentPass(PASS_RENDERING)
        layout_name = page.config.get('layout')
        if layout_name is None:
            layout_name = page.source.config.get('default_layout', 'default')
        null_names = ['', 'none', 'nil']
        if layout_name not in null_names:
            build_layout_data(page, page_data, contents)
            output = render_layout(layout_name, page, page_data)
        else:
            output = contents['content']

        rp = RenderedPage(page, ctx.uri, ctx.page_num)
        rp.data = page_data
        rp.content = output
        return rp
    finally:
        ctx.setCurrentPass(PASS_NONE)
        eis.popPage()


def render_page_segments(ctx):
    repo = ctx.app.env.rendered_segments_repository
    if repo:
        cache_key = ctx.uri
        return repo.get(
            cache_key,
            lambda: _do_render_page_segments_from_ctx(ctx),
            fs_cache_time=ctx.page.path_mtime)

    return _do_render_page_segments_from_ctx(ctx)


def _do_render_page_segments_from_ctx(ctx):
    eis = ctx.app.env.exec_info_stack
    eis.pushPage(ctx.page, ctx)
    ctx.setCurrentPass(PASS_FORMATTING)
    try:
        data_ctx = DataBuildingContext(ctx.page, page_num=ctx.page_num)
        page_data = build_page_data(data_ctx)
        return _do_render_page_segments(ctx.page, page_data)
    finally:
        ctx.setCurrentPass(PASS_NONE)
        eis.popPage()


def _do_render_page_segments(page, page_data):
    app = page.app
    engine_name = page.config.get('template_engine')
    format_name = page.config.get('format')

    engine = get_template_engine(app, engine_name)

    formatted_content = {}
    for seg_name, seg in page.raw_content.items():
        seg_text = ''
        for seg_part in seg.parts:
            part_format = seg_part.fmt or format_name
            try:
                part_text = engine.renderString(
                        seg_part.content, page_data,
                        filename=page.path)
            except TemplatingError as err:
                err.lineno += seg_part.line
                raise err

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
    default_exts = ['.' + e.lstrip('.')
                    for e in default_template_engine.EXTENSIONS]
    full_names = []
    for name in names:
        if '.' not in name:
            for ext in default_exts:
                full_names.append(name + ext)
        else:
            full_names.append(name)

    _, engine_name = os.path.splitext(full_names[0])
    engine_name = engine_name.lstrip('.')
    engine = get_template_engine(page.app, engine_name)

    try:
        output = engine.renderFile(full_names, layout_data)
    except TemplateNotFoundError as ex:
        msg = "Can't find template for page: %s\n" % page.path
        msg += "Looked for: %s" % ', '.join(full_names)
        raise Exception(msg) from ex
    return output


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
    for fmt in app.plugin_loader.getFormatters():
        if fmt.FORMAT_NAMES is None or format_name in fmt.FORMAT_NAMES:
            txt = fmt.render(format_name, txt)
            format_count += 1
            if fmt.OUTPUT_FORMAT is not None:
                format_name = fmt.OUTPUT_FORMAT
    if exact_format and format_count == 0:
        raise Exception("No such format: %s" % format_name)
    return txt

