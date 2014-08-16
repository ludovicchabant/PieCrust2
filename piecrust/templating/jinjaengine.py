import re
import time
import logging
import strict_rfc3339
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from jinja2.exceptions import TemplateSyntaxError
from jinja2.ext import Extension, Markup
from jinja2.nodes import CallBlock, Const
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from piecrust.rendering import format_text
from piecrust.routing import CompositeRouteFunction
from piecrust.templating.base import TemplateEngine, TemplateNotFoundError


logger = logging.getLogger(__name__)


class JinjaTemplateEngine(TemplateEngine):
    # Name `twig` is for backwards compatibility with PieCrust 1.x.
    ENGINE_NAMES = ['jinja', 'jinja2', 'twig']
    EXTENSIONS = ['jinja', 'jinja2', 'twig']

    def __init__(self):
        self.env = None

    def renderString(self, txt, data, filename=None, line_offset=0):
        self._ensureLoaded()
        tpl = self.env.from_string(txt)
        try:
            return tpl.render(data)
        except TemplateSyntaxError as tse:
            tse.lineno += line_offset
            if filename:
                tse.filename = filename
            import sys
            _, __, traceback = sys.exc_info()
            raise tse.with_traceback(traceback)

    def renderFile(self, paths, data):
        self._ensureLoaded()
        tpl = None
        logger.debug("Looking for template: %s" % paths)
        for p in paths:
            try:
                tpl = self.env.get_template(p)
                break
            except TemplateNotFound:
                pass
        if tpl is None:
            raise TemplateNotFoundError()
        return tpl.render(data)


    def _ensureLoaded(self):
        if self.env:
            return
        loader = FileSystemLoader(self.app.templates_dirs)
        self.env = PieCrustEnvironment(
                self.app,
                loader=loader,
                extensions=['jinja2.ext.autoescape',
                            PieCrustHighlightExtension,
                            PieCrustCacheExtension])


class PieCrustEnvironment(Environment):
    def __init__(self, app, *args, **kwargs):
        super(PieCrustEnvironment, self).__init__(*args, **kwargs)
        self.app = app
        self.globals.update({
                'fail': raise_exception})
        self.filters.update({
                'formatwith': self._formatWith,
                'markdown': lambda v: self._formatWith(v, 'markdown'),
                'textile': lambda v: self._formatWith(v, 'textile'),
                'nocache': add_no_cache_parameter,
                'wordcount': get_word_count,
                'stripoutertag': strip_outer_tag,
                'stripslash': strip_slash,
                'titlecase': title_case,
                'atomdate': get_atom_date,
                'date': get_date})
        # Backwards compatibility with PieCrust 1.x.
        self.globals.update({
                'pcfail': raise_exception})

        # Backwards compatibility with Twig.
        twig_compatibility_mode = app.config.get('jinja/twig_compatibility')
        if twig_compatibility_mode is None or twig_compatibility_mode is True:
            self.trim_blocks = True
            self.filters['raw'] = self.filters['safe']

        # Add route functions.
        for route in app.routes:
            name = route.template_func_name
            func = self.globals.get(name)
            if func is None:
                func = CompositeRouteFunction()
                func.addFunc(route)
                self.globals[name] = func
            elif isinstance(func, CompositeRouteFunction):
                self.globals[name].addFunc(route)
            else:
                raise Exception("Route function '%s' collides with an "
                                "existing function or template data." %
                                name)

    def _formatWith(self, value, format_name):
        return format_text(self.app, format_name, value)


def raise_exception(msg):
    raise Exception(msg)


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


def get_atom_date(value):
    return strict_rfc3339.timestamp_to_rfc3339_localoffset(int(value))


def get_date(value, fmt):
    return time.strftime(fmt, time.localtime(value))


class PieCrustHighlightExtension(Extension):
    tags = set(['highlight', 'geshi'])

    def __init__(self, environment):
        super(PieCrustHighlightExtension, self).__init__(environment)

    def parse(self, parser):
        lineno = next(parser.stream).lineno

        # Extract the language name.
        args = [parser.parse_expression()]

        # Extract optional arguments.
        kwarg_names = {'line_numbers': 0, 'use_classes': 0, 'class': 1, 'id': 1}
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


class PieCrustCacheExtension(Extension):
    tags = set(['pccache'])

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
        body = parser.parse_statements(['name:endpccache'], drop_needle=True)

        # now return a `CallBlock` node that calls our _cache_support
        # helper method on this extension.
        return CallBlock(self.call_method('_cache_support', args),
                               [], [], body).set_lineno(lineno)

    def _cache_support(self, name, caller):
        key = self.environment.piecrust_cache_prefix + name

        # try to load the block from the cache
        # if there is no fragment in the cache, render it and store
        # it in the cache.
        rv = self.environment.piecrust_cache.get(key)
        if rv is not None:
            return rv
        rv = caller()
        self.environment.piecrust_cache[key] = rv
        return rv

