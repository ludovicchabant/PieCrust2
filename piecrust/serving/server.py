import io
import os
import gzip
import time
import os.path
import hashlib
import logging
from werkzeug.exceptions import (
    NotFound, MethodNotAllowed, InternalServerError, HTTPException)
from werkzeug.wrappers import Request, Response
from jinja2 import FileSystemLoader, Environment
from piecrust import CACHE_DIR, RESOURCES_DIR
from piecrust.rendering import RenderingContext, render_page
from piecrust.routing import RouteNotFoundError
from piecrust.serving.util import (
    content_type_map, make_wrapped_file_response, get_requested_page,
    get_app_for_server)
from piecrust.sources.base import SourceNotFoundError


logger = logging.getLogger(__name__)


class PieCrustServer(object):
    """ A WSGI application that serves a PieCrust website.
    """
    def __init__(self, appfactory, **kwargs):
        self.server = _ServerImpl(appfactory, **kwargs)

    def __call__(self, environ, start_response):
        return self.server._run_request(environ, start_response)


class MultipleNotFound(HTTPException):
    """ Represents a 404 (not found) error that tried to serve one or
        more pages. It will report which pages it tried to serve
        before failing.
    """
    code = 404

    def __init__(self, description, nfes):
        super(MultipleNotFound, self).__init__(description)
        self._nfes = nfes

    def get_description(self, environ=None):
        from werkzeug.utils import escape
        desc = '<p>' + self.description + '</p>'
        desc += '<p>'
        for nfe in self._nfes:
            desc += '<li>' + escape(str(nfe)) + '</li>'
        desc += '</p>'
        return desc


class _ServerImpl(object):
    """ The PieCrust server.
    """
    def __init__(self, appfactory,
                 enable_debug_info=True,
                 root_url='/',
                 static_preview=True):
        self.appfactory = appfactory
        self.enable_debug_info = enable_debug_info
        self.root_url = root_url
        self.static_preview = static_preview
        self._out_dir = os.path.join(
            appfactory.root_dir,
            CACHE_DIR,
            (appfactory.cache_key or 'default'),
            'server')

    def _run_request(self, environ, start_response):
        try:
            response = self._try_run_request(environ)
            return response(environ, start_response)
        except Exception as ex:
            if self.appfactory.debug:
                raise
            return self._handle_error(ex, environ, start_response)

    def _try_run_request(self, environ):
        request = Request(environ)

        # We don't support anything else than GET requests since we're
        # previewing something that will be static later.
        if self.static_preview and request.method != 'GET':
            logger.error("Only GET requests are allowed, got %s" %
                         request.method)
            raise MethodNotAllowed()

        # Handle requests to a pipeline-built asset right away.
        response = self._try_serve_asset(environ, request)
        if response is not None:
            return response

        # Same for page assets.
        response = self._try_serve_page_asset(
            self.appfactory.root_dir, environ, request)
        if response is not None:
            return response

        # Create the app for this request.
        app = get_app_for_server(self.appfactory,
                                 root_url=self.root_url)
        if (app.config.get('server/enable_debug_info') and
                self.enable_debug_info and
                '!debug' in request.args):
            app.config.set('site/show_debug_info', True)

        # Let's try to serve a page.
        try:
            response = self._try_serve_page(app, environ, request)
            return response
        except (RouteNotFoundError, SourceNotFoundError) as ex:
            raise NotFound() from ex
        except HTTPException:
            raise
        except Exception as ex:
            if app.debug:
                logger.exception(ex)
                raise
            logger.error(str(ex))
            msg = "There was an error trying to serve: %s" % request.path
            raise InternalServerError(msg) from ex

    def _try_serve_asset(self, environ, request):
        offset = len(self.root_url)
        rel_req_path = request.path[offset:].replace('/', os.sep)
        if request.path.startswith('/_cache/'):
            # Some stuff needs to be served directly from the cache directory,
            # like LESS CSS map files.
            full_path = os.path.join(self.appfactory.root_dir, rel_req_path)
        else:
            full_path = os.path.join(self._out_dir, rel_req_path)

        try:
            return make_wrapped_file_response(environ, request, full_path)
        except OSError:
            return None

    def _try_serve_page_asset(self, app_root_dir, environ, request):
        if not request.path.startswith(self.root_url + '_asset/'):
            return None

        offset = len(self.root_url + '_asset/')
        full_path = os.path.join(app_root_dir, request.path[offset:])

        try:
            return make_wrapped_file_response(environ, request, full_path)
        except OSError:
            return None

    def _try_serve_page(self, app, environ, request):
        # Find a matching page.
        req_page = get_requested_page(app, request.path)

        # If we haven't found any good match, report all the places we didn't
        # find it at.
        if req_page.page is None:
            msg = "Can't find path for '%s':" % request.path
            raise MultipleNotFound(msg, req_page.not_found_errors)

        # We have a page, let's try to render it.
        render_ctx = RenderingContext(req_page.page,
                                      sub_num=req_page.sub_num,
                                      force_render=True)
        req_page.page.source.prepareRenderContext(render_ctx)

        # Render the page.
        rendered_page = render_page(render_ctx)

        # Start doing stuff.
        page = rendered_page.page
        rp_content = rendered_page.content

        # Profiling.
        if app.config.get('site/show_debug_info'):
            now_time = time.perf_counter()
            timing_info = (
                '%8.1f ms' %
                ((now_time - app.env.start_time) * 1000.0))
            rp_content = rp_content.replace(
                '__PIECRUST_TIMING_INFORMATION__', timing_info)

        # Build the response.
        response = Response()

        etag = hashlib.md5(rp_content.encode('utf8')).hexdigest()
        if not app.debug and etag in request.if_none_match:
            response.status_code = 304
            return response

        response.set_etag(etag)
        response.content_md5 = etag

        cache_control = response.cache_control
        if app.debug:
            cache_control.no_cache = True
            cache_control.must_revalidate = True
        else:
            cache_time = (page.config.get('cache_time') or
                          app.config.get('site/cache_time'))
            if cache_time:
                cache_control.public = True
                cache_control.max_age = cache_time

        content_type = page.config.get('content_type')
        if content_type and '/' not in content_type:
            mimetype = content_type_map.get(content_type, content_type)
        else:
            mimetype = content_type
        if mimetype:
            response.mimetype = mimetype

        if ('gzip' in request.accept_encodings and
                app.config.get('site/enable_gzip')):
            try:
                with io.BytesIO() as gzip_buffer:
                    with gzip.open(gzip_buffer, mode='wt',
                                   encoding='utf8') as gzip_file:
                        gzip_file.write(rp_content)
                    rp_content = gzip_buffer.getvalue()
                    response.content_encoding = 'gzip'
            except Exception:
                logger.error("Error compressing response, "
                             "falling back to uncompressed.")
        response.set_data(rp_content)

        return response

    def _handle_error(self, exception, environ, start_response):
        code = 500
        if isinstance(exception, HTTPException):
            code = exception.code

        path = 'error'
        if isinstance(exception, (NotFound, MultipleNotFound)):
            path += '404'

        descriptions = self._get_exception_descriptions(exception)

        env = Environment(loader=ErrorMessageLoader())
        template = env.get_template(path)
        context = {'details': descriptions}
        response = Response(template.render(context), mimetype='text/html')
        response.status_code = code
        return response(environ, start_response)

    def _get_exception_descriptions(self, exception):
        desc = []
        while exception is not None:
            if isinstance(exception, MultipleNotFound):
                desc += [str(e) for e in exception._nfes]
            elif isinstance(exception, HTTPException):
                desc.append(exception.get_description())
            else:
                desc.append(str(exception))

            inner_ex = exception.__cause__
            if inner_ex is None:
                inner_ex = exception.__context__
            exception = inner_ex
        return desc


class ErrorMessageLoader(FileSystemLoader):
    def __init__(self):
        base_dir = os.path.join(RESOURCES_DIR, 'messages')
        super(ErrorMessageLoader, self).__init__(base_dir)

    def get_source(self, env, template):
        template += '.html'
        return super(ErrorMessageLoader, self).get_source(env, template)

