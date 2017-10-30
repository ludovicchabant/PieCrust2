import os
import os.path
import time
import logging
import yaml
from piecrust.dataproviders.pageiterator import PageIterator
from piecrust.processing.base import SimpleFileProcessor


logger = logging.getLogger(__name__)


SITEMAP_HEADER = \
"""<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""
SITEMAP_FOOTER = "</urlset>\n"

SITEURL_HEADER =     "  <url>\n"  # NOQA: E222
SITEURL_LOC =        "    <loc>%s</loc>\n"  # NOQA: E222
SITEURL_LASTMOD =    "    <lastmod>%s</lastmod>\n"  # NOQA: E222
SITEURL_CHANGEFREQ = "    <changefreq>%s</changefreq>\n"  # NOQA: E222
SITEURL_PRIORITY =   "    <priority>%0.1f</priority>\n"  # NOQA: E222
SITEURL_FOOTER =     "  </url>\n"  # NOQA: E222


class SitemapProcessor(SimpleFileProcessor):
    PROCESSOR_NAME = 'sitemap'

    def __init__(self):
        super(SitemapProcessor, self).__init__({'sitemap': 'xml'})
        self._start_time = None

    def onPipelineStart(self, ctx):
        self._start_time = time.time()

    def _doProcess(self, in_path, out_path):
        with open(in_path, 'r') as fp:
            sitemap = yaml.load(fp)

        try:
            with open(out_path, 'w') as fp:
                fp.write(SITEMAP_HEADER)
                self._writeManualLocs(sitemap, fp)
                self._writeAutoLocs(sitemap, fp)
                fp.write(SITEMAP_FOOTER)
        except:
            # If an exception occurs, delete the output file otherwise
            # the pipeline will think the output was correctly produced.
            if os.path.isfile(out_path):
                logger.debug("Error occured, removing output sitemap.")
                os.unlink(out_path)
            raise

        return True

    def _writeManualLocs(self, sitemap, fp):
        locs = sitemap.setdefault('locations', None)
        if not locs:
            return

        logger.debug("Generating manual sitemap entries.")
        for loc in locs:
            self._writeEntry(loc, fp)

    def _writeAutoLocs(self, sitemap, fp):
        source_names = sitemap.setdefault('autogen', None)
        if not source_names:
            return

        cur_time = strftime_iso8601(time.time())
        for name in source_names:
            logger.debug("Generating automatic sitemap entries for '%s'." %
                         name)
            source = self.app.getSource(name)
            if source is None:
                raise Exception("No such source: %s" % name)

            it = PageIterator(source)
            for page in it:
                uri = page['url']
                sm_cfg = page.get('sitemap')

                args = {'url': uri, 'lastmod': cur_time}
                if sm_cfg:
                    args.update(sm_cfg)

                self._writeEntry(args, fp)

    def _writeEntry(self, args, fp):
        fp.write(SITEURL_HEADER)
        fp.write(SITEURL_LOC % args['url'])
        if 'lastmod' in args:
            fp.write(SITEURL_LASTMOD % args['lastmod'])
        if 'changefreq' in args:
            fp.write(SITEURL_CHANGEFREQ % args['changefreq'])
        if 'priority' in args:
            fp.write(SITEURL_PRIORITY % args['priority'])
        fp.write(SITEURL_FOOTER)


def strftime_iso8601(t):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))

