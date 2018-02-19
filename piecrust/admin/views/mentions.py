import os
import os.path
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from flask import current_app, g, request, make_response, abort
from ..blueprint import foodtruck_bp
from piecrust.app import PieCrustFactory
from piecrust.serving.util import get_requested_page


logger = logging.getLogger(__name__)


@foodtruck_bp.route('/webmention', methods=['POST'])
def post_webmention():
    # Basic validation of source/target.
    src_url = request.form.get('source')
    tgt_url = request.form.get('target')
    if not src_url or not tgt_url:
        logger.error("No source or target specified.")
        abort(400)
    if src_url.lower().rstrip('/') == tgt_url.lower().rstrip('/'):
        logger.error("Source and target are the same.")
        abort(400)

    # See if we need to do this synchronously or asynchronously, and other
    # things we should know up-front.
    wmcfg = g.site.piecrust_app.config.get('webmention')
    if wmcfg.get('use_task_queue') is True:
        tasks_dir = os.path.join(g.site.piecrust_app.root_dir, '_tasks')
        _ensure_dir(tasks_dir)
        task_data = {
            'type': 'webmention',
            'data': {'source': src_url, 'target': tgt_url}}
        task_path = os.path.join(tasks_dir, '%s.json' % int(time.time()))
        with open(task_path, 'w', encoding='utf8') as fp:
            json.dump(task_data, fp)
        return make_response("Webmention queued.", 202, [])

    # Find if we have a page at the target URL.
    # To do that we need to spin up a PieCrust app that knows how the website
    # works. Because the website might have been baked with custom settings
    # (usually the site root URL) there's a good chance we need to apply
    # some variants, which the user can specify in the config.
    pcappfac = PieCrustFactory(
        current_app.config['FOODTRUCK_ROOT_DIR'],
        cache_key='webmention')
    if wmcfg.get('config_variant'):
        pcappfac.config_variants = [wmcfg.get('config_variant')]
    if wmcfg.get('config_variants'):
        pcappfac.config_variants = list(wmcfg.get('config_variants'))
    if wmcfg.get('config_values'):
        pcappfac.config_values = list(wmcfg.get('config_values').items())
    pcapp = pcappfac.create()
    try:
        req_page = get_requested_page(pcapp, tgt_url)
        if req_page.page is None:
            abort(404)
    except Exception as ex:
        logger.error("Can't check webmention target page: %s" % tgt_url)
        logger.exception(ex)
        abort(404)

    # Grab the source URL's contents and see if anything references the
    # target (ours) URL.
    src_t = requests.get(src_url)
    src_html = BeautifulSoup(src_t.text, 'html.parser')
    for link in src_html.find_all('a'):
        href = link.get('href')
        if href == tgt_url:
            break
    else:
        logger.error("Source '%s' doesn't link to target: %s" %
                     (src_url, tgt_url))
        abort(400)

    # Find something to quote for this webmention. We find an `h-entry`
    # to get a title, excerpt, and/or text.
    blurb = None
    hentry = src_html.find(class_='h-entry')
    if hentry:
        try:
            pname = hentry.find(class_='p-name')
            pauthor = hentry.find(class_='p-author')
            blurb = {
                'pname': _bs4_contents_str(pname),
                'pauthor': _bs4_contents_str(pauthor)}
        except:  # NOQA
            logger.error("Couldn't get h-entry info.")

    dirname, _ = os.path.splitext(req_page.page.content_spec)
    dirname += '-assets'
    _ensure_dir(dirname)
    mention_path = os.path.join(dirname, 'mentions.json')
    try:
        with open(mention_path, 'r', encoding='utf-8') as fp:
            mention = json.load(fp)
    except IOError:
        mention = {'mentions': []}

    for m in mention['mentions']:
        if m['source'] == src_url:
            return

    new_mention = {'source': src_url}
    if blurb:
        new_mention.update(blurb)

    mention['mentions'].append(new_mention)

    with open(mention_path, 'w', encoding='utf-8') as fp:
        json.dump(mention, fp)
    logger.info("Received webmention from: %s" % src_url)

    return make_response(("Webmention received.", 202, []))


def _bs4_contents_str(node):
    return ''.join([str(c).strip() for c in node.contents])


def _ensure_dir(path, mode=0o775):
    try:
        os.makedirs(path, mode=mode, exist_ok=True)
    except OSError:
        pass

