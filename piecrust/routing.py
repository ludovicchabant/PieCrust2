import re
import logging


logger = logging.getLogger(__name__)


route_re = re.compile(r'%((?P<qual>path):)?(?P<name>\w+)%')
template_func_re = re.compile(r'^(?P<name>\w+)\((?P<first_arg>\w+)(?P<other_args>.*)\)\s*$')
template_func_arg_re = re.compile(r',\s*(?P<arg>\w+)')


class IRouteMetadataProvider(object):
    def getRouteMetadata(self):
        raise NotImplementedError()


class Route(object):
    """ Information about a route for a PieCrust application.
        Each route defines the "shape" of an URL and how it maps to
        sources and taxonomies.
    """
    def __init__(self, app, cfg):
        self.app = app
        uri = cfg['url']
        self.uri_root = app.config.get('site/root').rstrip('/') + '/'
        self.uri_pattern = uri.lstrip('/')
        self.uri_format = route_re.sub(self._uriFormatRepl, self.uri_pattern)
        p = route_re.sub(self._uriPatternRepl, self.uri_pattern)
        self.uri_re = re.compile(p)
        self.source_name = cfg['source']
        self.taxonomy = cfg.get('taxonomy')
        self.required_source_metadata = []
        for m in route_re.finditer(uri):
            self.required_source_metadata.append(m.group('name'))
        self.template_func = None
        self.template_func_name = None
        self.template_func_args = []
        self._createTemplateFunc(cfg.get('func'))

    @property
    def source(self):
        for src in self.app.sources:
            if src.name == self.source_name:
                return src
        raise Exception("Can't find source '%s' for route '%'." % (
                self.source_name, self.uri))

    @property
    def source_realm(self):
        return self.source.realm

    def isMatch(self, source_metadata):
        return True

    def getUri(self, source_metadata, provider=None):
        if provider:
            source_metadata = dict(source_metadata)
            source_metadata.update(provider.getRouteMetadata())
        #TODO: fix this hard-coded shit
        for key in ['year', 'month', 'day']:
            if key in source_metadata and isinstance(source_metadata[key], str):
                source_metadata[key] = int(source_metadata[key])
        return self.uri_root + (self.uri_format % source_metadata)

    def _uriFormatRepl(self, m):
        name = m.group('name')
        #TODO: fix this hard-coded shit
        if name == 'year':
            return '%(year)04d'
        if name == 'month':
            return '%(month)02d'
        if name == 'day':
            return '%(day)02d'
        return '%(' + name + ')s'

    def _uriPatternRepl(self, m):
        name = m.group('name')
        qualifier = m.group('qual')
        if qualifier == 'path':
            return r'(?P<%s>.*)' % name
        return r'(?P<%s>[^/\?]+)' % name

    def _createTemplateFunc(self, func_def):
        if func_def is None:
            return

        m = template_func_re.match(func_def)
        if m is None:
            raise Exception("Template function definition for route '%s' "
                            "has invalid syntax: %s" %
                            (self.uri_pattern, func_def))

        self.template_func_name = m.group('name')
        self.template_func_args.append(m.group('first_arg'))
        arg_list = m.group('other_args')
        if arg_list:
            self.template_func_args += template_func_arg_re.findall(arg_list)

        if self.taxonomy:
            # This will be a taxonomy route function... this means we can
            # have a variable number of parameters, but only one parameter
            # definition, which is the value.
            if len(self.template_func_args) != 1:
                raise Exception("Route '%s' is a taxonomy route and must have "
                                "only one argument, which is the term value." %
                                self.uri_pattern)

            def template_func(*args):
                if len(args) == 0:
                    raise Exception(
                            "Route function '%s' expected at least one "
                            "argument." % func_def)

                # Term combinations can be passed as an array, or as multiple
                # arguments.
                values = args
                if len(args) == 1 and isinstance(args[0], list):
                    values = args[0]

                # We need to register this use of a taxonomy term.
                if len(values) == 1:
                    registered_values = values[0]
                else:
                    registered_values = tuple(values)
                eis = self.app.env.exec_info_stack
                eis.current_page_info.render_ctx.used_taxonomy_terms.add(
                        (self.source_name, self.taxonomy, registered_values))

                if len(values) == 1:
                    str_values = values[0]
                else:
                    str_values = '/'.join(values)
                term_name = self.template_func_args[0]
                metadata = {term_name: str_values}

                return self.getUri(metadata)

        else:
            # Normal route function.
            def template_func(*args):
                if len(args) != len(self.template_func_args):
                    raise Exception(
                            "Route function '%s' expected %d arguments, "
                            "got %d." %
                            (func_def, len(self.template_func_args),
                                len(args)))
                metadata = {}
                for arg_name, arg_val in zip(self.template_func_args, args):
                    metadata[arg_name] = arg_val
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
        if len(args) == len(self._arg_names):
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

