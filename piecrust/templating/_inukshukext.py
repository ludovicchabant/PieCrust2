import io
import re
import time
from inukshuk.ext import Extension, StatementNode
from inukshuk.ext.core import filter_make_xml_date, filter_safe
from inukshuk.lexer import (
    TOKEN_ID_STRING_SINGLE_QUOTES, TOKEN_ID_STRING_DOUBLE_QUOTES)
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from piecrust.data.paginator import Paginator
from piecrust.rendering import format_text


class PieCrustExtension(Extension):
    def __init__(self, app):
        self.app = app

    def setupEngine(self, engine):
        engine.piecrust_app = self.app
        engine.piecrust_cache = {}

    def getGlobals(self):
        return {
            'highlight_css': get_highlight_css}

    def getFilters(self):
        return {
            'paginate': self._paginate,
            'formatwith': self._formatWith,
            'markdown': lambda v: self._formatWith(v, 'markdown'),
            'textile': lambda v: self._formatWith(v, 'textile'),
            'nocache': add_no_cache_parameter,
            'stripoutertag': strip_outer_tag,
            'stripslash': strip_slash,
            'atomdate': filter_make_xml_date,
            'raw': filter_safe
        }

    def getTests(self):
        return {}

    def getStatementNodes(self):
        return [
            PieCrustHighlightStatementNode,
            PieCrustGeshiStatementNode,
            PieCrustCacheStatementNode,
            PieCrustFormatStatementNode]

    def _paginate(self, value, items_per_page=5):
        ctx = self.app.env.render_ctx_stack.current_ctx
        if ctx is None or ctx.page is None:
            raise Exception("Can't paginate when no page has been pushed "
                            "on the execution stack.")
        return Paginator(value, ctx.page,
                         sub_num=ctx.sub_num,
                         items_per_page=items_per_page)

    def _formatWith(self, value, format_name):
        return format_text(self.app, format_name, value)


def add_no_cache_parameter(value, param_name='t', param_value=None):
    if not param_value:
        param_value = time.time()
    if '?' in value:
        value += '&'
    else:
        value += '?'
    value += '%s=%s' % (param_name, param_value)
    return value


def strip_outer_tag(value, tag=None):
    tag_pattern = '[a-z]+[a-z0-9]*'
    if tag is not None:
        tag_pattern = re.escape(tag)
    pat = r'^\<' + tag_pattern + r'\>(.*)\</' + tag_pattern + '>$'
    m = re.match(pat, value)
    if m:
        return m.group(1)
    return value


def strip_slash(value):
    return value.rstrip('/')


class PieCrustFormatStatementNode(StatementNode):
    name = 'pcformat'
    compiler_imports = ['import io',
                        'from piecrust.rendering import format_text']

    def __init__(self):
        super().__init__()
        self.format = None

    def parse(self, parser):
        self.format = parser.expectIdentifier()
        parser.skipWhitespace()
        parser.expectStatementEnd()
        parser.parseUntilStatement(self, ['endpcformat'])
        parser.expectIdentifier('endpcformat')

    def render(self, ctx, data, out):
        with io.StringIO() as tmp:
            inner_out = tmp.write
            for c in self.children:
                c.render(ctx, data, inner_out)

            text = format_text(ctx.engine.piecrust_app, self.format,
                               tmp.getvalue(), exact_format=True)
            out(text)

    def compile(self, ctx, out):
        out.indent().write('with io.StringIO() as tmp:\n')
        out.push(False)
        out.indent().write('prev_out_write = out_write\n')
        out.indent().write('out_write = tmp.write\n')
        for c in self.children:
            c.compile(ctx, out)
        out.indent().write('out_write = prev_out_write\n')
        out.indent().write(
            'text = format_text(ctx_engine.piecrust_app, %s, tmp.getvalue(), '
            'exact_format=True)\n' % repr(self.format))
        out.indent().write('out_write(text)\n')
        out.pull()


class PieCrustHighlightStatementNode(StatementNode):
    name = 'highlight'
    endname = 'endhighlight'
    compiler_imports = [
        'from pygments import highlight',
        'from pygments.formatters import HtmlFormatter',
        'from pygments.lexers import get_lexer_by_name, guess_lexer']

    def __init__(self):
        super().__init__()
        self.lang = None

    def parse(self, parser):
        self.lang = parser.expectAny([TOKEN_ID_STRING_SINGLE_QUOTES,
                                      TOKEN_ID_STRING_DOUBLE_QUOTES])
        parser.skipWhitespace()
        parser.expectStatementEnd()

        parser.parseUntilStatement(self, self.endname)
        parser.expectIdentifier(self.endname)

    def render(self, ctx, data, out):
        with io.StringIO() as tmp:
            inner_out = tmp.write
            for c in self.children:
                c.render(ctx, data, inner_out)

            raw_text = tmp.getvalue()

        if self.lang is None:
            lexer = guess_lexer(raw_text)
        else:
            lexer = get_lexer_by_name(self.lang, stripall=False)

        formatter = HtmlFormatter()
        code = highlight(raw_text, lexer, formatter)
        out(code)

    def compile(self, ctx, out):
        out.indent().write('with io.StringIO() as tmp:\n')
        out.push(False)
        out.indent().write('prev_out_write = out_write\n')
        out.indent().write('out_write = tmp.write\n')
        for c in self.children:
            c.compile(ctx, out)
        out.indent().write('out_write = prev_out_write\n')
        out.indent().write('raw_text = tmp.getvalue()\n')
        out.pull()
        if self.lang is None:
            out.indent().write('lexer = guess_lexer(raw_text)\n')
        else:
            out.indent().write(
                'lexer = get_lexer_by_name(%s, stripall=False)\n' %
                repr(self.lang))
        out.indent().write('formatter = HtmlFormatter()\n')
        out.indent().write('code = highlight(raw_text, lexer, formatter)\n')
        out.indent().write('out_write(code)\n')


class PieCrustGeshiStatementNode(PieCrustHighlightStatementNode):
    name = 'geshi'
    endname = 'endgeshi'


def get_highlight_css(style_name='default', class_name='.highlight'):
    return HtmlFormatter(style=style_name).get_style_defs(class_name)


class PieCrustCacheStatementNode(StatementNode):
    name = 'pccache'
    compiler_imports = ['import io']

    def __init__(self):
        super().__init__()
        self.cache_key = None

    def parse(self, parser):
        self.cache_key = parser.expectString()
        parser.skipWhitespace()
        parser.expectStatementEnd()

        parser.parseUntilStatement(self, 'endpccache')
        parser.expectIdentifier('endpccache')

    def render(self, ctx, data, out):
        raise Exception("No implemented")

        # exc_stack = ctx.engine.piecrust_app.env.exec_info_stack
        # render_ctx = exc_stack.current_page_info.render_ctx
        # rdr_pass = render_ctx.current_pass_info

        # pair = ctx.engine.piecrust_cache.get(self.cache_key)
        # if pair is not None:
        #     rdr_pass.used_source_names.update(pair[1])
        #     return pair[0]

        # prev_used = rdr_pass.used_source_names.copy()

        # with io.StringIO() as tmp:
        #     inner_out = tmp.write
        #     for c in self.children:
        #         c.render(ctx, data, inner_out)

        #     raw_text = tmp.getvalue()

        # after_used = rdr_pass.used_source_names.copy()
        # used_delta = after_used.difference(prev_used)
        # ctx.engine.piecrust_cache[self.cache_key] = (raw_text, used_delta)

        # return raw_text

    def compile(self, ctx, out):
        out.indent().write(
            'ctx_stack = ctx.engine.piecrust_app.env.render_ctx_stack\n')
        out.indent().write(
            'render_ctx = ctx_stack.current_ctx\n')
        out.indent().write(
            'rdr_pass = render_ctx.current_pass_info\n')

        pair_var = ctx.varname('pair')
        out.indent().write(
            '%s = ctx.engine.piecrust_cache.get(%s)\n' %
            (pair_var, repr(self.cache_key)))
        out.indent().write(
            'if %s is not None:\n' % pair_var)
        out.push().write(
            'rdr_pass.used_source_names.update(%s[1])\n' % pair_var)
        out.indent().write('out_write(%s[0])\n' % pair_var)
        out.pull()
        out.indent().write('else:\n')

        tmp_var = ctx.varname('tmp')
        prev_used_var = ctx.varname('prev_used')
        prev_out_write_var = ctx.varname('prev_out_write')
        prev_out_write_escaped_var = ctx.varname('prev_out_write_escaped')

        out.push().write(
            '%s = rdr_pass.used_source_names.copy()\n' % prev_used_var)
        out.indent().write(
            'with io.StringIO() as %s:\n' % tmp_var)
        out.push().write(
            '%s = out_write\n' % prev_out_write_var)
        out.indent().write(
            '%s = out_write_escaped\n' % prev_out_write_escaped_var)
        out.indent().write(
            'out_write = %s.write\n' % tmp_var)
        out.indent().write(
            'out_write_escaped = ctx.engine._getWriteEscapeFunc(out_write)\n')
        for c in self.children:
            c.compile(ctx, out)

        out.indent().write(
            'out_write_escaped = %s\n' % prev_out_write_escaped_var)
        out.indent().write(
            'out_write = %s\n' % prev_out_write_var)
        out.indent().write(
            'raw_text = %s.getvalue()\n' % tmp_var)
        out.pull()

        out.indent().write(
            'after_used = rdr_pass.used_source_names.copy()\n')
        out.indent().write(
            'used_delta = after_used.difference(%s)\n' % prev_used_var)
        out.indent().write(
            'ctx.engine.piecrust_cache[%s] = (raw_text, used_delta)\n' %
            repr(self.cache_key))
        out.indent().write('out_write(raw_text)\n')
        out.pull()
