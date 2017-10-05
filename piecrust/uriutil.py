import re
import os.path
import logging


logger = logging.getLogger(__name__)


def multi_replace(text, replacements):
    reps = dict((re.escape(k), v) for k, v in replacements.items())
    pattern = re.compile("|".join(list(reps.keys())))
    return pattern.sub(lambda m: reps[re.escape(m.group(0))], text)


def split_uri(app, uri):
    root = app.config.get('site/root')
    uri_root = uri[:len(root)]
    if uri_root != root:
        raise Exception("URI '%s' is not a full URI, expected root '%s'." %
                        (uri, root))
    uri = uri[len(root):]
    return uri_root, uri


def split_sub_uri(app, uri):
    root = app.config.get('site/root')
    if not uri.startswith(root):
        raise Exception("URI '%s' is not a full URI, expected root '%s'." %
                        (uri, root))

    pretty_urls = app.config.get('site/pretty_urls')
    trailing_slash = app.config.get('site/trailing_slash')
    if not pretty_urls:
        uri, ext = os.path.splitext(uri)
    else:
        uri = uri.rstrip('/')

    page_num = 1
    pgn_suffix_re = app.config.get('__cache/pagination_suffix_re')
    m = re.search(pgn_suffix_re, uri)
    if m:
        uri = uri[:m.start()]
        page_num = int(m.group('num'))

    if len(uri) < len(root):
        # The only reasons the URI could have gotten shorter are:
        # - if the regexp "ate" the trailing slash of the root.
        # - if we stripped the trailing slash on a root URL.
        uri += '/'

    if len(uri) > len(root):
        # Now if we don't have a root URI, make it conform to the rules
        # (re-add the extension, or re-add the trailing slash).
        if not pretty_urls:
            uri += ext
        elif trailing_slash:
            uri += '/'

    return uri, page_num


def uri_to_title(slug):
    slug = re.sub(r'[\-_]', ' ', slug)
    return slug.title()

