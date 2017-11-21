from jinja2.ext import Extension, Markup
from jinja2.lexer import Token, describe_token
from jinja2.nodes import CallBlock, Const
from compressinja.html import HtmlCompressor, StreamProcessContext
from piecrust.rendering import format_text


class PieCrustFormatExtension(Extension):
    tags = set(['pcformat'])

    def __init__(self, environment):
        super(PieCrustFormatExtension, self).__init__(environment)

    def parse(self, parser):
        lineno = next(parser.stream).lineno
        args = [parser.parse_expression()]
        body = parser.parse_statements(['name:endpcformat'], drop_needle=True)
        return CallBlock(self.call_method('_formatTimed', args),
                         [], [], body).set_lineno(lineno)

    def _formatTimed(self, format_name, caller=None):
        with self.environment.app.env.stats.timerScope(
                'JinjaTemplateEngine_extensions'):
            return self._format(format_name, caller)

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

        return CallBlock(self.call_method('_highlightTimed', args, kwargs),
                         [], [], body).set_lineno(lineno)

    def _highlightTimed(self, lang, line_numbers=False, use_classes=False,
                        css_class=None, css_id=None, caller=None):
        with self.environment.app.env.stats.timerScope(
                'JinjaTemplateEngine_extensions'):
            return self._highlight(lang, line_numbers, use_classes,
                                   css_class, css_id, caller)

    def _highlight(self, lang, line_numbers=False, use_classes=False,
                   css_class=None, css_id=None, caller=None):
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import get_lexer_by_name, guess_lexer

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
    from pygments.formatters import HtmlFormatter
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

        # now return a `CallBlock` node that calls our _renderCache
        # helper method on this extension.
        return CallBlock(self.call_method('_renderCacheTimed', args),
                         [], [], body).set_lineno(lineno)

    def _renderCacheTimed(self, name, caller):
        with self.environment.app.env.stats.timerScope(
                'JinjaTemplateEngine_extensions'):
            return self._renderCache(name, caller)

    def _renderCache(self, name, caller):
        key = self.environment.piecrust_cache_prefix + name

        rcs = self.environment.app.env.render_ctx_stack
        ctx = rcs.current_ctx

        # try to load the block from the cache
        # if there is no fragment in the cache, render it and store
        # it in the cache.
        pair = self.environment.piecrust_cache.get(key)
        if pair is not None:
            for usn in pair[1]:
                ctx.addUsedSource(usn)
            return pair[0]

        prev_used = set(ctx.current_used_source_names)
        rv = caller()
        after_used = set(ctx.current_used_source_names)
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
