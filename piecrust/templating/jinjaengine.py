import re
import time
import os.path
import hashlib
import logging
import email.utils
import strict_rfc3339
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from jinja2.exceptions import TemplateSyntaxError
from jinja2.ext import Extension, Markup
from jinja2.lexer import Token, describe_token
from jinja2.nodes import CallBlock, Const
from compressinja.html import HtmlCompressor, StreamProcessContext
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from piecrust.data.paginator import Paginator
from piecrust.environment import AbortedSourceUseError
from piecrust.rendering import format_text
from piecrust.templating.base import (TemplateEngine, TemplateNotFoundError,
                                      TemplatingError)
from piecrust.uriutil import multi_replace


logger = logging.getLogger(__name__)


class JinjaTemplateEngine(TemplateEngine):
    # Name `twig` is for backwards compatibility with PieCrust 1.x.
    ENGINE_NAMES = ['jinja', 'jinja2', 'j2', 'twig']
    EXTENSIONS = ['html', 'jinja', 'jinja2', 'j2', 'twig']

    def __init__(self):
        self.env = None

    def renderSegmentPart(self, path, seg_part, data):
        self._ensureLoaded()

        if not _string_needs_render(seg_part.content):
            return seg_part.content

        part_path = _make_segment_part_path(path, seg_part.offset)
        self.env.loader.segment_parts_cache[part_path] = (
                path, seg_part.content)
        try:
            tpl = self.env.get_template(part_path)
        except TemplateSyntaxError as tse:
            raise self._getTemplatingError(tse, filename=path)
        except TemplateNotFound:
            raise TemplateNotFoundError()

        try:
            return tpl.render(data)
        except TemplateSyntaxError as tse:
            raise self._getTemplatingError(tse)
        except AbortedSourceUseError:
            raise
        except Exception as ex:
            if self.app.debug:
                raise
            msg = "Error rendering Jinja markup"
            rel_path = os.path.relpath(path, self.app.root_dir)
            raise TemplatingError(msg, rel_path) from ex

    def renderFile(self, paths, data):
        self._ensureLoaded()
        tpl = None
        logger.debug("Looking for template: %s" % paths)
        rendered_path = None
        for p in paths:
            try:
                tpl = self.env.get_template(p)
                rendered_path = p
                break
            except TemplateSyntaxError as tse:
                raise self._getTemplatingError(tse)
            except TemplateNotFound:
                pass

        if tpl is None:
            raise TemplateNotFoundError()

        try:
            return tpl.render(data)
        except TemplateSyntaxError as tse:
            raise self._getTemplatingError(tse)
        except AbortedSourceUseError:
            raise
        except Exception as ex:
            msg = "Error rendering Jinja markup"
            rel_path = os.path.relpath(rendered_path, self.app.root_dir)
            raise TemplatingError(msg, rel_path) from ex

    def _getTemplatingError(self, tse, filename=None):
        filename = tse.filename or filename
        if filename and os.path.isabs(filename):
            filename = os.path.relpath(filename, self.env.app.root_dir)
        err = TemplatingError(str(tse), filename, tse.lineno)
        raise err from tse

    def _ensureLoaded(self):
        if self.env:
            return

        # Get the list of extensions to load.
        ext_names = self.app.config.get('jinja/extensions', [])
        if not isinstance(ext_names, list):
            ext_names = [ext_names]

        # Turn on autoescape by default.
        autoescape = self.app.config.get('twig/auto_escape')
        if autoescape is not None:
            logger.warning("The `twig/auto_escape` setting is now called "
                           "`jinja/auto_escape`.")
        else:
            autoescape = self.app.config.get('jinja/auto_escape', True)
        if autoescape:
            ext_names.append('autoescape')

        # Create the final list of extensions.
        extensions = [
                PieCrustHighlightExtension,
                PieCrustCacheExtension,
                PieCrustSpacelessExtension,
                PieCrustFormatExtension]
        for n in ext_names:
            if '.' not in n:
                n = 'jinja2.ext.' + n
            extensions.append(n)
        for je in self.app.plugin_loader.getTemplateEngineExtensions('jinja'):
            extensions.append(je)

        # Create the Jinja environment.
        logger.debug("Creating Jinja environment with folders: %s" %
                     self.app.templates_dirs)
        loader = PieCrustLoader(self.app.templates_dirs)
        self.env = PieCrustEnvironment(
                self.app,
                loader=loader,
                extensions=extensions)


def _string_needs_render(txt):
    index = txt.find('{')
    while index >= 0:
        ch = txt[index + 1]
        if ch == '{' or ch == '%':
            return True
        index = txt.find('{', index + 1)
    return False


def _make_segment_part_path(path, start):
    return '$part=%s:%d' % (path, start)


class PieCrustLoader(FileSystemLoader):
    def __init__(self, searchpath, encoding='utf-8'):
        super(PieCrustLoader, self).__init__(searchpath, encoding)
        self.segment_parts_cache = {}

    def get_source(self, environment, template):
        if template.startswith('$part='):
            filename, seg_part = self.segment_parts_cache[template]

            mtime = os.path.getmtime(filename)

            def uptodate():
                try:
                    return os.path.getmtime(filename) == mtime
                except OSError:
                    return False

            return seg_part, filename, uptodate

        return super(PieCrustLoader, self).get_source(environment, template)


class PieCrustEnvironment(Environment):
    def __init__(self, app, *args, **kwargs):
        self.app = app

        # Before we create the base Environement, let's figure out the options
        # we want to pass to it.
        twig_compatibility_mode = app.config.get('jinja/twig_compatibility')

        # Disable auto-reload when we're baking.
        if app.config.get('baker/is_baking'):
            kwargs.setdefault('auto_reload', False)

        # Let the user override most Jinja options via the site config.
        for name in ['block_start_string', 'block_end_string',
                     'variable_start_string', 'variable_end_string',
                     'comment_start_string', 'comment_end_string',
                     'line_statement_prefix', 'line_comment_prefix',
                     'trim_blocks', 'lstrip_blocks',
                     'newline_sequence', 'keep_trailing_newline']:
            val = app.config.get('jinja/' + name)
            if val is not None:
                kwargs.setdefault(name, val)

        # Twig trims blocks.
        if twig_compatibility_mode is True:
            kwargs['trim_blocks'] = True

        # All good! Create the Environment.
        super(PieCrustEnvironment, self).__init__(*args, **kwargs)

        # Now add globals and filters.
        self.globals.update({
                'now': get_now_date(),
                'fail': raise_exception,
                'highlight_css': get_highlight_css})

        self.filters.update({
                'keys': get_dict_keys,
                'values': get_dict_values,
                'paginate': self._paginate,
                'formatwith': self._formatWith,
                'markdown': lambda v: self._formatWith(v, 'markdown'),
                'textile': lambda v: self._formatWith(v, 'textile'),
                'nocache': add_no_cache_parameter,
                'wordcount': get_word_count,
                'stripoutertag': strip_outer_tag,
                'stripslash': strip_slash,
                'titlecase': title_case,
                'md5': make_md5,
                'atomdate': get_xml_date,
                'xmldate': get_xml_date,
                'emaildate': get_email_date,
                'date': get_date})

        # Backwards compatibility with Twig.
        if twig_compatibility_mode is True:
            self.filters['raw'] = self.filters['safe']
            self.globals['pcfail'] = raise_exception

    def _paginate(self, value, items_per_page=5):
        cpi = self.app.env.exec_info_stack.current_page_info
        if cpi is None or cpi.page is None or cpi.render_ctx is None:
            raise Exception("Can't paginate when no page has been pushed "
                            "on the execution stack.")
        return Paginator(cpi.page, value,
                         page_num=cpi.render_ctx.page_num,
                         items_per_page=items_per_page)

    def _formatWith(self, value, format_name):
        return format_text(self.app, format_name, value)


def raise_exception(msg):
    raise Exception(msg)


def get_dict_keys(value):
    if isinstance(value, list):
        return [i[0] for i in value]
    return value.keys()


def get_dict_values(value):
    if isinstance(value, list):
        return [i[1] for i in value]
    return value.values()


def add_no_cache_parameter(value, param_name='t', param_value=None):
    if not param_value:
        param_value = time.time()
    if '?' in value:
        value += '&'
    else:
        value += '?'
    value += '%s=%s' % (param_name, param_value)
    return value


def get_word_count(value):
    return len(value.split())


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


def title_case(value):
    return value.title()


def make_md5(value):
    return hashlib.md5(value.lower().encode('utf8')).hexdigest()


def get_xml_date(value):
    """ Formats timestamps like 1985-04-12T23:20:50.52Z
    """
    if value == 'now':
        value = time.time()
    return strict_rfc3339.timestamp_to_rfc3339_localoffset(int(value))


def get_email_date(value, localtime=False):
    """ Formats timestamps like Fri, 09 Nov 2001 01:08:47 -0000
    """
    if value == 'now':
        value = time.time()
    return email.utils.formatdate(value, localtime=localtime)


def get_now_date():
    return time.time()


def get_date(value, fmt):
    if value == 'now':
        value = time.time()
    if '%' not in fmt:
        suggest = php_format_to_strftime_format(fmt)
        if suggest != fmt:
            suggest_message = ("You probably want a format that looks "
                               "like: '%s'." % suggest)
        else:
            suggest_message = ("We can't suggest a proper date format "
                               "for you right now, though.")
        raise Exception("Got incorrect date format: '%s\n"
                        "PieCrust 1 date formats won't work in PieCrust 2. "
                        "%s\n"
                        "Please check the `strftime` formatting page here: "
                        "https://docs.python.org/3/library/datetime.html"
                        "#strftime-and-strptime-behavior" %
                        (fmt, suggest_message))
    return time.strftime(fmt, time.localtime(value))


class PieCrustFormatExtension(Extension):
    tags = set(['pcformat'])

    def __init__(self, environment):
        super(PieCrustFormatExtension, self).__init__(environment)

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        args = [parser.parse_expression()]
        body = parser.parse_statements(['name:endpcformat'], drop_needle=True)
        return CallBlock(self.call_method('_format', args),
                         [], [], body).set_lineno(lineno)

    def _format(self, format_name, caller=None):
        body = caller()
        text = format_text(self.environment.app,
                           format_name,
                           Markup(body.rstrip()).unescape(),
                           exact_format=True)
        return text


class PieCrustHighlightExtension(Extension):
    tags = set(['highlight', 'geshi'])

    def __init__(self, environment):
        super(PieCrustHighlightExtension, self).__init__(environment)

    def parse(self, parser):
        lineno = next(parser.stream).lineno

        # Extract the language name.
        args = [parser.parse_expression()]

        # Extract optional arguments.
        kwarg_names = {'line_numbers': 0, 'use_classes': 0, 'class': 1,
                       'id': 1}
        kwargs = {}
        while not parser.stream.current.test('block_end'):
            name = parser.stream.expect('name')
            if name.value not in kwarg_names:
                raise Exception("'%s' is not a valid argument for the code "
                                "highlighting tag." % name.value)
            if kwarg_names[name.value] == 0:
                kwargs[name.value] = Const(True)
            elif parser.stream.skip_if('assign'):
                kwargs[name.value] = parser.parse_expression()

        # body of the block
        body = parser.parse_statements(['name:endhighlight', 'name:endgeshi'],
                                       drop_needle=True)

        return CallBlock(self.call_method('_highlight', args, kwargs),
                         [], [], body).set_lineno(lineno)

    def _highlight(self, lang, line_numbers=False, use_classes=False,
                   css_class=None, css_id=None, caller=None):
        # Try to be mostly compatible with Jinja2-highlight's settings.
        body = caller()

        if lang is None:
            lexer = guess_lexer(body)
        else:
            lexer = get_lexer_by_name(lang, stripall=False)

        if css_class is None:
            try:
                css_class = self.environment.jinja2_highlight_cssclass
            except AttributeError:
                pass

        if css_class is not None:
            formatter = HtmlFormatter(cssclass=css_class,
                                      linenos=line_numbers)
        else:
            formatter = HtmlFormatter(linenos=line_numbers)

        code = highlight(Markup(body.rstrip()).unescape(), lexer, formatter)
        return code


def get_highlight_css(style_name='default', class_name='.highlight'):
    return HtmlFormatter(style=style_name).get_style_defs(class_name)


class PieCrustCacheExtension(Extension):
    tags = set(['pccache', 'cache'])

    def __init__(self, environment):
        super(PieCrustCacheExtension, self).__init__(environment)
        environment.extend(
            piecrust_cache_prefix='',
            piecrust_cache={}
        )

    def parse(self, parser):
        # the first token is the token that started the tag.  In our case
        # we only listen to ``'pccache'`` so this will be a name token with
        # `pccache` as value.  We get the line number so that we can give
        # that line number to the nodes we create by hand.
        lineno = next(parser.stream).lineno

        # now we parse a single expression that is used as cache key.
        args = [parser.parse_expression()]

        # now we parse the body of the cache block up to `endpccache` and
        # drop the needle (which would always be `endpccache` in that case)
        body = parser.parse_statements(['name:endpccache', 'name:endcache'],
                                       drop_needle=True)

        # now return a `CallBlock` node that calls our _cache_support
        # helper method on this extension.
        return CallBlock(self.call_method('_cache_support', args),
                         [], [], body).set_lineno(lineno)

    def _cache_support(self, name, caller):
        key = self.environment.piecrust_cache_prefix + name

        exc_stack = self.environment.app.env.exec_info_stack
        render_ctx = exc_stack.current_page_info.render_ctx
        rdr_pass = render_ctx.current_pass_info

        # try to load the block from the cache
        # if there is no fragment in the cache, render it and store
        # it in the cache.
        pair = self.environment.piecrust_cache.get(key)
        if pair is not None:
            rdr_pass.used_source_names.update(pair[1])
            return pair[0]

        pair = self.environment.piecrust_cache.get(key)
        if pair is not None:
            rdr_pass.used_source_names.update(pair[1])
            return pair[0]

        prev_used = rdr_pass.used_source_names.copy()
        rv = caller()
        after_used = rdr_pass.used_source_names.copy()
        used_delta = after_used.difference(prev_used)
        self.environment.piecrust_cache[key] = (rv, used_delta)
        return rv


class PieCrustSpacelessExtension(HtmlCompressor):
    """ A re-implementation of `SelectiveHtmlCompressor` so that we can
        both use `strip` or `spaceless` in templates.
    """
    def filter_stream(self, stream):
        ctx = StreamProcessContext(stream)
        strip_depth = 0
        while 1:
            if stream.current.type == 'block_begin':
                for tk in ['strip', 'spaceless']:
                    change = self._processToken(ctx, stream, tk)
                    if change != 0:
                        strip_depth += change
                        if strip_depth < 0:
                            ctx.fail('Unexpected tag end%s' % tk)
                        break
            if strip_depth > 0 and stream.current.type == 'data':
                ctx.token = stream.current
                value = self.normalize(ctx)
                yield Token(stream.current.lineno, 'data', value)
            else:
                yield stream.current
            next(stream)

    def _processToken(self, ctx, stream, test_token):
        change = 0
        if (stream.look().test('name:%s' % test_token) or
                stream.look().test('name:end%s' % test_token)):
            stream.skip()
            if stream.current.value == test_token:
                change = 1
            else:
                change = -1
            stream.skip()
            if stream.current.type != 'block_end':
                ctx.fail('expected end of block, got %s' %
                         describe_token(stream.current))
            stream.skip()
        return change


def php_format_to_strftime_format(fmt):
    replacements = {
            'd': '%d',
            'D': '%a',
            'j': '%d',
            'l': '%A',
            'w': '%w',
            'z': '%j',
            'W': '%W',
            'F': '%B',
            'm': '%m',
            'M': '%b',
            'n': '%m',
            'y': '%Y',
            'Y': '%y',
            'g': '%I',
            'G': '%H',
            'h': '%I',
            'H': '%H',
            'i': '%M',
            's': '%S',
            'e': '%Z',
            'O': '%z',
            'c': '%Y-%m-%dT%H:%M:%SZ'}
    return multi_replace(fmt, replacements)

