import re
import os.path
import copy
import logging
import urllib.parse
from werkzeug.utils import cached_property


logger = logging.getLogger(__name__)


route_re = re.compile(r'%((?P<qual>[\w\d]+):)?(?P<var>\+)?(?P<name>\w+)%')
route_esc_re = re.compile(r'\\%((?P<qual>[\w\d]+)\\:)?(?P<var>\\\+)?(?P<name>\w+)\\%')
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

        # Determine the parameters for the route function.
        self.func_name = self._validateFuncName(cfg.get('func'))
        self.func_parameters = []
        self.func_has_variadic_parameter = False
        variadic_param_idx = -1
        for m in route_re.finditer(self.uri_pattern):
            name = m.group('name')
            if m.group('var'):
                self.func_has_variadic_parameter = True
                variadic_param_idx = len(self.func_parameters)

            self.func_parameters.append(name)

        if (variadic_param_idx >= 0 and
                variadic_param_idx != len(self.func_parameters) - 1):
            raise Exception(
                "Only the last route URL parameter can be variadic. "
                "Got: %s" % self.uri_pattern)

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
        return set(self.func_parameters).issubset(route_metadata.keys())

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
            missing_keys = set(self.func_parameters) - matched_keys
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

    def execTemplateFunc(self, *args):
        fixed_param_count = len(self.func_parameters)
        if self.func_has_variadic_parameter:
            fixed_param_count -= 1

        if len(args) < fixed_param_count:
            raise Exception(
                    "Route function '%s' expected %d arguments, "
                    "got %d: %s" %
                    (self.func_name, fixed_param_count, len(args), args))

        if self.func_has_variadic_parameter:
            coerced_args = list(args[:fixed_param_count])
            if len(args) > fixed_param_count:
                var_arg = tuple(args[fixed_param_count:])
                coerced_args.append(var_arg)
        else:
            coerced_args = args

        metadata = {}
        for arg_name, arg_val in zip(self.func_parameters, coerced_args):
            metadata[arg_name] = self._coerceRouteParameter(
                    arg_name, arg_val)

        if self.is_generator_route:
            self.generator.onRouteFunctionUsed(self, metadata)

        return self.getUri(metadata)

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
        if qual == 'path' or m.group('var'):
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
                        (name, param_type, val))
        if param_type == 'path':
            return val
        raise Exception("Unknown route parameter type: %s" % param_type)

    def _validateFuncName(self, name):
        if not name:
            return None
        i = name.find('(')
        if i >= 0:
            name = name[:i]
            logger.warning(
                "Route function names shouldn't contain the list of arguments "
                "anymore -- just specify '%s'." % name)
        return name


class CompositeRouteFunction(object):
    def __init__(self):
        self._routes = []
        self._arg_names = None

    def addFunc(self, route):
        if self._arg_names is None:
            self._arg_names = list(route.func_parameters)

        if route.func_parameters != self._arg_names:
            raise Exception("Cannot merge route function with arguments '%s' "
                            "with route function with arguments '%s'." %
                            (route.func_parameters, self._arg_names))
        self._routes.append(route)

    def __call__(self, *args, **kwargs):
        if len(self._routes) == 1 or len(args) == len(self._arg_names):
            return self._routes[0].execTemplateFunc(*args, **kwargs)

        if len(args) == len(self._arg_names) + 1:
            f_args = args[:-1]
            for r in self._routes:
                if r.source_name == args[-1]:
                    return r.execTemplateFunc(*f_args, **kwargs)
            raise Exception("No such source: %s" % args[-1])

        raise Exception("Incorrect number of arguments for route function. "
                        "Expected '%s', got '%s'" % (self._arg_names, args))

