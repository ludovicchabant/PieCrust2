import os
import os.path
import json
import logging
from piecrust.tasks.base import TaskRunner


logger = logging.getLogger(__name__)


class InvalidMentionTargetError(Exception):
    pass


class SourceDoesntLinkToTargetError(Exception):
    pass


class DuplicateMentionError(Exception):
    pass


class MentionTaskRunner(TaskRunner):
    TASK_TYPE = 'mention'

    def runTask(self, data, ctx):
        import json
        import requests
        from bs4 import BeautifulSoup
        from piecrust.app import PieCrustFactory
        from piecrust.serving.util import get_requested_page

        src_url = data['source']
        tgt_url = data['target']

        # Find if we have a page at the target URL.  To do that we need to spin
        # up a PieCrust app that knows how the website works. Because the
        # website might have been baked with custom settings (usually the site
        # root URL) there's a good chance we need to apply some variants, which
        # the user can specify in the config.
        pcappfac = PieCrustFactory(self.app.root_dir,
                                   cache_key='webmention')
        wmcfg = self.app.config.get('webmention')
        if wmcfg.get('config_variant'):
            pcappfac.config_variants = [wmcfg.get('config_variant')]
        if wmcfg.get('config_variants'):
            pcappfac.config_variants = list(wmcfg.get('config_variants'))
        if wmcfg.get('config_values'):
            pcappfac.config_values = list(wmcfg.get('config_values').items())
        pcapp = pcappfac.create()
        logger.debug("Locating page: %s" % tgt_url)
        try:
            req_page = get_requested_page(pcapp, tgt_url)
            if req_page.page is None:
                raise InvalidMentionTargetError()
        except Exception as ex:
            logger.error("Can't check webmention target page: %s" % tgt_url)
            logger.exception(ex)
            raise InvalidMentionTargetError()

        # Grab the source URL's contents and see if anything references the
        # target (ours) URL.
        logger.debug("Fetching mention source: %s" % src_url)
        src_t = requests.get(src_url)
        src_html = BeautifulSoup(src_t.text, 'html.parser')
        for link in src_html.find_all('a'):
            href = link.get('href')
            if href == tgt_url:
                break
        else:
            logger.error("Source '%s' doesn't link to target: %s" %
                         (src_url, tgt_url))
            raise SourceDoesntLinkToTargetError()

        # Load the previous mentions and find any pre-existing mention from the
        # source URL.
        mention_path, mention_data = _load_page_mentions(req_page.page)
        for m in mention_data['mentions']:
            if m['source'] == src_url:
                logger.error("Duplicate mention found from: %s" % src_url)
                raise DuplicateMentionError()

        # Make the new mention.
        new_mention = {'source': src_url}

        # Parse the microformats on the page, see if there's anything
        # interesting we can use.
        mf2_info = _get_mention_info_from_mf2(src_url, src_html)
        if mf2_info:
            new_mention.update(mf2_info)

        # Add the new mention.
        mention_data['mentions'].append(new_mention)

        with open(mention_path, 'w', encoding='utf-8') as fp:
            json.dump(mention_data, fp)
        logger.info("Received webmention from: %s" % src_url)


def _get_mention_info_from_mf2(base_url, bs_html):
    import mf2py
    from urllib.parse import urljoin

    mf2 = mf2py.parse(bs_html)
    mf2_items = mf2.get('items')
    if not mf2_items:
        return None

    hentry = next(filter(
        lambda i: 'h-entry' in i['type'],
        mf2_items), None)
    if not hentry:
        return None

    info = {}
    hentry_props = hentry['properties']

    pnames = hentry_props.get('name')
    if pnames:
        info['name'] = pnames[0]

    urls = hentry_props.get('url')
    if urls:
        info['url'] = urljoin(base_url, urls[0])

    pubdates = hentry_props.get('published')
    if pubdates:
        info['published'] = pubdates[0]

    contents = hentry_props.get('content')
    if contents:
        info['content'] = contents[0]['html']

    authors = hentry_props.get('author')
    if authors:
        hcard = next(filter(
            lambda i: 'h-card' in i['type'],
            authors), None)
        if hcard:
            hcard_props = hcard['properties']
            hcard_names = hcard_props.get('name')
            if hcard_names:
                info['author_name'] = hcard_names[0]
            hcard_photos = hcard_props.get('photo')
            if hcard_photos:
                info['author_photo'] = urljoin(base_url, hcard_photos[0])
            hcard_urls = hcard_props.get('url')
            if hcard_urls:
                info['author_url'] = urljoin(base_url, hcard_urls[0])

    return info


def _load_page_mentions(page):
    from piecrust.pathutil import ensure_dir

    logger.debug("Loading page mentions for: %s" % page.content_spec)
    dirname, _ = os.path.splitext(page.content_spec)
    dirname += '-assets'
    ensure_dir(dirname)
    mention_path = os.path.join(dirname, 'mentions.json')
    try:
        with open(mention_path, 'r', encoding='utf-8') as fp:
            return mention_path, json.load(fp)
    except IOError:
        return mention_path, {'mentions': []}
