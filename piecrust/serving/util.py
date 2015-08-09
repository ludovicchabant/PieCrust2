import re
import os.path
import hashlib
import logging
import datetime
from werkzeug.wrappers import Response
from werkzeug.wsgi import wrap_file


logger = logging.getLogger(__name__)


def load_mimetype_map():
    mimetype_map = {}
    sep_re = re.compile(r'\s+')
    path = os.path.join(os.path.dirname(__file__), 'mime.types')
    with open(path, 'r') as f:
        for line in f:
            tokens = sep_re.split(line)
            if len(tokens) > 1:
                for t in tokens[1:]:
                    mimetype_map[t] = tokens[0]
    return mimetype_map


def make_wrapped_file_response(environ, request, path):
    logger.debug("Serving %s" % path)

    # Check if we can return a 304 status code.
    mtime = os.path.getmtime(path)
    etag_str = '%s$$%s' % (path, mtime)
    etag = hashlib.md5(etag_str.encode('utf8')).hexdigest()
    if etag in request.if_none_match:
        response = Response()
        response.status_code = 304
        return response

    wrapper = wrap_file(environ, open(path, 'rb'))
    response = Response(wrapper)
    _, ext = os.path.splitext(path)
    response.set_etag(etag)
    response.last_modified = datetime.datetime.fromtimestamp(mtime)
    response.mimetype = mimetype_map.get(
            ext.lstrip('.'), 'text/plain')
    response.direct_passthrough = True
    return response


mimetype_map = load_mimetype_map()
content_type_map = {
        'html': 'text/html',
        'xml': 'text/xml',
        'txt': 'text/plain',
        'text': 'text/plain',
        'css': 'text/css',
        'xhtml': 'application/xhtml+xml',
        'atom': 'application/atom+xml',  # or 'text/xml'?
        'rss': 'application/rss+xml',    # or 'text/xml'?
        'json': 'application/json'}

