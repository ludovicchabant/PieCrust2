import re
import os.path
import copy
import logging
import urllib.parse
from werkzeug.utils import cached_property


logger = logging.getLogger(__name__)


route_re = re.compile(r'%((?P<qual>[\w\d]+):)?(?P<name>\w+)%')
route_esc_re = re.compile(r'\\%((?P<qual>[\w\d]+)\\:)?(?P<name>\w+)\\%')
template_func_re = re.compile(r'^(?P<name>\w+)\((?P<args>.*)\)\s*$')
template_func_arg_re = re.compile(r'((?P<qual>[\w\d]+):)?(?P<arg>\+?\w+)')
ugly_url_cleaner = re.compile(r'\.html$')


class RouteNotFoundError(Exception):
    pass


class InvalidRouteError(Exception):
    pass


def create_route_metadata(page):
    route_metadata = copy.deepcopy(page.source_metadata)
    route_metadata.update(page.getRouteMetadata())
    return route_metadata


class IRouteMetadataProvider(object):
    def getRouteMetadata(self):
        raise NotImplementedError()


ROUTE_TYPE_SOURCE = 0
ROUTE_TYPE_GENERATOR = 1


class Route(object):
    """ Information about a route for a PieCrust application.
        Each route defines the "shape" of an URL and how it maps to
        sources and generators.
    """
    def __init__(self, app, cfg):
        self.app = app

        self.source_name = cfg.get('source')
        self.generator_name = cfg.get('generator')
        if not self.source_name and not self.generator_name:
            raise InvalidRouteError(
                    "Both `source` and `generator` are specified.")

        self.pretty_urls = app.config.get('site/pretty_urls')
        self.trailing_slash = app.config.get('site/trailing_slash')
        self.show_debug_info = app.config.get('site/show_debug_info')
        self.pagination_suffix_format = app.config.get(
                '__cache/pagination_suffix_format')
        self.uri_root = app.config.get('site/root')

        uri = cfg['url']
        self.uri_pattern = uri.lstrip('/')
        self.uri_format = route_re.sub(self._uriFormatRepl, self.uri_pattern)

        # Get the straight-forward regex for matching this URI pattern.
        p = route_esc_re.sub(self._uriPatternRepl,
                             re.escape(self.uri_pattern)) + '$'
        self.uri_re = re.compile(p)

        # Get the types of the route parameters.
        self.param_types = {}
        for m in route_re.finditer(self.uri_pattern):
            qual = m.group('qual')
            if qual:
                self.param_types[str(m.group('name'))] = qual

        # If the URI pattern has a 'path'-type component, we'll need to match
        # the versions for which that component is empty. So for instance if
        # we have `/foo/%path:bar%`, we may need to match `/foo` (note the
        # lack of a trailing slash). We have to build a special pattern (in
        # this case without that trailing slash) to match those situations.
        # (maybe there's a better way to do it but I can't think of any
        # right now)
        uri_pattern_no_path = (
                route_re.sub(self._uriNoPathRepl, self.uri_pattern)
                .replace('//', '/')
                .rstrip('/'))
        if uri_pattern_no_path != self.uri_pattern:
            p = route_esc_re.sub(self._uriPatternRepl,
                                 re.escape(uri_pattern_no_path)) + '$'
            self.uri_re_no_path = re.compile(p)
        else:
            self.uri_re_no_path = None

        self.required_route_metadata = set()
        for m in route_re.finditer(self.uri_pattern):
            self.required_route_metadata.add(m.group('name'))

        self.template_func = None
        self.template_func_name = None
        self.template_func_args = []
        self.template_func_vararg = None
        self._createTemplateFunc(cfg.get('func'))

    @property
    def route_type(self):
        if self.source_name:
            return ROUTE_TYPE_SOURCE
        elif self.generator_name:
            return ROUTE_TYPE_GENERATOR
        else:
            raise InvalidRouteError()

    @property
    def is_source_route(self):
        return self.route_type == ROUTE_TYPE_SOURCE

    @property
    def is_generator_route(self):
        return self.route_type == ROUTE_TYPE_GENERATOR

    @cached_property
    def source(self):
        if not self.is_source_route:
            return InvalidRouteError("This is not a source route.")
        for src in self.app.sources:
            if src.name == self.source_name:
                return src
        raise Exception("Can't find source '%s' for route '%s'." % (
                self.source_name, self.uri))

    @cached_property
    def generator(self):
        if not self.is_generator_route:
            return InvalidRouteError("This is not a generator route.")
        for gen in self.app.generators:
            if gen.name == self.generator_name:
                return gen
        raise Exception("Can't find generator '%s' for route '%s'." % (
                self.generator_name, self.uri))

    def matchesMetadata(self, route_metadata):
        return self.required_route_metadata.issubset(route_metadata.keys())

    def matchUri(self, uri, strict=False):
        if not uri.startswith(self.uri_root):
            raise Exception("The given URI is not absolute: %s" % uri)
        uri = uri[len(self.uri_root):]

        if not self.pretty_urls:
            uri = ugly_url_cleaner.sub('', uri)
        elif self.trailing_slash:
            uri = uri.rstrip('/')

        route_metadata = None
        m = self.uri_re.match(uri)
        if m:
            route_metadata = m.groupdict()
        if self.uri_re_no_path:
            m = self.uri_re_no_path.match(uri)
            if m:
                route_metadata = m.groupdict()
        if route_metadata is None:
            return None

        if not strict:
            # When matching URIs, if the URI is a match but is missing some
            # metadata, fill those up with empty strings. This can happen if,
            # say, a route's pattern is `/foo/%slug%`, and we're matching an
            # URL like `/foo`.
            matched_keys = set(route_metadata.keys())
            missing_keys = self.required_route_metadata - matched_keys
            for k in missing_keys:
                route_metadata[k] = ''

        for k in route_metadata:
            route_metadata[k] = self._coerceRouteParameter(
                    k, route_metadata[k])

        return route_metadata

    def getUri(self, route_metadata, *, sub_num=1):
        route_metadata = dict(route_metadata)
        for k in route_metadata:
            route_metadata[k] = self._coerceRouteParameter(
                    k, route_metadata[k])

        uri = self.uri_format % route_metadata
        suffix = None
        if sub_num > 1:
            # Note that we know the pagination suffix starts with a slash.
            suffix = self.pagination_suffix_format % {'num': sub_num}

        if self.pretty_urls:
            # Output will be:
            # - `subdir/name`
            # - `subdir/name/2`
            # - `subdir/name.ext`
            # - `subdir/name.ext/2`
            if suffix:
                if uri == '':
                    uri = suffix.lstrip('/')
                else:
                    uri = uri.rstrip('/') + suffix
            if self.trailing_slash and uri != '':
                uri = uri.rstrip('/') + '/'
        else:
            # Output will be:
            # - `subdir/name.html`
            # - `subdir/name/2.html`
            # - `subdir/name.ext`
            # - `subdir/name/2.ext`
            if uri == '':
                if suffix:
                    uri = suffix.lstrip('/') + '.html'
            else:
                base_uri, ext = os.path.splitext(uri)
                if not ext:
                    ext = '.html'
                if suffix:
                    uri = base_uri + suffix + ext
                else:
                    uri = base_uri + ext

        uri = self.uri_root + urllib.parse.quote(uri)

        if self.show_debug_info:
            uri += '?!debug'

        return uri

    def _uriFormatRepl(self, m):
        qual = m.group('qual')
        name = m.group('name')
        if qual == 'int4':
            return '%%(%s)04d' % name
        elif qual == 'int2':
            return '%%(%s)02d' % name
        return '%%(%s)s' % name

    def _uriPatternRepl(self, m):
        name = m.group('name')
        qual = m.group('qual')
        if qual == 'path':
            return r'(?P<%s>[^\?]*)' % name
        elif qual == 'int4':
            return r'(?P<%s>\d{4})' % name
        elif qual == 'int2':
            return r'(?P<%s>\d{2})' % name
        return r'(?P<%s>[^/\?]+)' % name

    def _uriNoPathRepl(self, m):
        name = m.group('name')
        qualifier = m.group('qual')
        if qualifier == 'path':
            return ''
        return r'(?P<%s>[^/\?]+)' % name

    def _coerceRouteParameter(self, name, val):
        param_type = self.param_types.get(name)
        if param_type is None:
            return val
        if param_type in ['int', 'int2', 'int4']:
            try:
                return int(val)
            except ValueError:
                raise Exception(
                        "Expected route parameter '%s' to be of type "
                        "'%s', but was: %s" %
                        (k, param_type, route_metadata[k]))
        if param_type == 'path':
            return val
        raise Exception("Unknown route parameter type: %s" % param_type)

    def _createTemplateFunc(self, func_def):
        if func_def is None:
            return

        m = template_func_re.match(func_def)
        if m is None:
            raise Exception("Template function definition for route '%s' "
                            "has invalid syntax: %s" %
                            (self.uri_pattern, func_def))

        self.template_func_name = m.group('name')
        self.template_func_args = []
        arg_list = m.group('args')
        if arg_list:
            self.template_func_args = []
            for m2 in template_func_arg_re.finditer(arg_list):
                self.template_func_args.append(m2.group('arg'))
            for i in range(len(self.template_func_args) - 1):
                if self.template_func_args[i][0] == '+':
                    raise Exception("Only the last route parameter can be a "
                                    "variable argument (prefixed with `+`)")

        if (self.template_func_args and
                self.template_func_args[-1][0] == '+'):
            self.template_func_vararg = self.template_func_args[-1][1:]

        def template_func(*args):
            is_variable = (self.template_func_vararg is not None)
            if not is_variable and len(args) != len(self.template_func_args):
                raise Exception(
                        "Route function '%s' expected %d arguments, "
                        "got %d: %s" %
                        (func_def, len(self.template_func_args),
                            len(args), args))
            elif is_variable and len(args) < len(self.template_func_args):
                raise Exception(
                        "Route function '%s' expected at least %d arguments, "
                        "got %d: %s" %
                        (func_def, len(self.template_func_args),
                            len(args), args))

            metadata = {}
            non_var_args = list(self.template_func_args)
            if is_variable:
                del non_var_args[-1]

            for arg_name, arg_val in zip(non_var_args, args):
                metadata[arg_name] = self._coerceRouteParameter(
                        arg_name, arg_val)

            if is_variable:
                metadata[self.template_func_vararg] = []
                for i in range(len(non_var_args), len(args)):
                    metadata[self.template_func_vararg].append(args[i])

            if self.is_generator_route:
                self.generator.onRouteFunctionUsed(self, metadata)

            return self.getUri(metadata)

        self.template_func = template_func


class CompositeRouteFunction(object):
    def __init__(self):
        self._funcs = []
        self._arg_names = None

    def addFunc(self, route):
        if self._arg_names is None:
            self._arg_names = sorted(route.template_func_args)

        if sorted(route.template_func_args) != self._arg_names:
            raise Exception("Cannot merge route function with arguments '%s' "
                            "with route function with arguments '%s'." %
                            (route.template_func_args, self._arg_names))
        self._funcs.append((route, route.template_func))

    def __call__(self, *args, **kwargs):
        if len(self._funcs) == 1 or len(args) == len(self._arg_names):
            f = self._funcs[0][1]
            return f(*args, **kwargs)

        if len(args) == len(self._arg_names) + 1:
            f_args = args[:-1]
            for r, f in self._funcs:
                if r.source_name == args[-1]:
                    return f(f_args, **kwargs)
            raise Exception("No such source: %s" % args[-1])

        raise Exception("Incorrect number of arguments for route function. "
                        "Expected '%s', got '%s'" % (self._arg_names, args))

