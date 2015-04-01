import re
import os.path
import string
import logging
import functools


logger = logging.getLogger(__name__)


class UriError(Exception):
    def __init__(self, uri):
        super(UriError, self).__init__("Invalid URI: %s" % uri)


@functools.total_ordering
class UriInfo(object):
    def __init__(self, uri, source, args, taxonomy=None, page_num=1):
        self.uri = uri
        self.source = source
        self.args = args
        self.taxonomy = taxonomy
        self.page_num = page_num

    def __eq__(self, other):
        return ((self.uri, self.source, self.args, self.taxonomy,
                self.page_num) ==
            (other.uri, other.source, other.args, other.taxonomy,
                other.page_num))

    def __lt__(self, other):
        return ((self.uri, self.source, self.args, self.taxonomy,
                self.page_num) <
            (other.uri, other.source, other.args, other.taxonomy,
                other.page_num))


pagenum_pattern = re.compile(r'/(\d+)/?$')


def parse_uri(routes, uri):
    if uri.find('..') >= 0:
        raise UriError(uri)

    page_num = 1
    match = pagenum_pattern.search(uri)
    if match is not None:
        uri = uri[:match.start()]
        page_num = int(match.group(1))

    uri = '/' + uri.strip('/')

    for rn, rc in routes.items():
        pattern = route_to_pattern(rn)
        m = re.match(pattern, uri)
        if m is not None:
            args = m.groupdict()
            return UriInfo(uri, rc['source'], args, rc.get('taxonomy'),
                    page_num)

    return None


r2p_pattern = re.compile(r'%(\w+)%')


def route_to_pattern(route):
    return r2p_pattern.sub(r'(?P<\1>[\w\-]+)', route)


def multi_replace(text, replacements):
    reps = dict((re.escape(k), v) for k, v in replacements.items())
    pattern = re.compile("|".join(list(reps.keys())))
    return pattern.sub(lambda m: reps[re.escape(m.group(0))], text)


def split_uri(app, uri):
    root = app.config.get('site/root')
    uri_root = uri[:len(root)]
    if uri_root != root:
        raise Exception("URI '%s' is not a full URI." % uri)
    uri = uri[len(root):]
    return uri_root, uri


def split_sub_uri(app, uri):
    root = app.config.get('site/root')
    if not uri.startswith(root):
        raise Exception("URI '%s' is not a full URI." % uri)

    pretty_urls = app.config.get('site/pretty_urls')
    if not pretty_urls:
        uri, ext = os.path.splitext(uri)

    page_num = 1
    pgn_suffix_re = app.config.get('__cache/pagination_suffix_re')
    m = re.search(pgn_suffix_re, uri)
    if m:
        uri = uri[:m.start()]
        if uri == '':
            uri = '/'
        page_num = int(m.group('num'))

    if not pretty_urls:
        uri += ext

    return uri, page_num

