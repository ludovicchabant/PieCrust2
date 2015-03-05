import time
import logging
import yaml
from piecrust.processing.base import SimpleFileProcessor


logger = logging.getLogger(__name__)


SITEMAP_HEADER = \
"""<?xml version="1.0" encoding="utf-8"?>
<urlset
  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""
SITEMAP_FOOTER = "</urlset>\n"

SITEURL_HEADER =     "  <url>\n"
SITEURL_LOC =        "    <loc>%s</loc>\n"
SITEURL_LASTMOD =    "    <lastmod>%s</lastmod>\n"
SITEURL_CHANGEFREQ = "    <changefreq>%s</changefreq>\n"
SITEURL_PRIORITY =   "    <priority>%f</priority>\n"
SITEURL_FOOTER =     "  </url>\n"


class SitemapProcessor(SimpleFileProcessor):
    PROCESSOR_NAME = 'sitemap'

    def __init__(self):
        super(SitemapProcessor, self).__init__({'sitemap': 'xml'})
        self._start_time = None

    def onPipelineStart(self, pipeline):
        self._start_time = time.time()

    def _doProcess(self, in_path, out_path):
        with open(in_path, 'r') as fp:
            sitemap = yaml.load(fp)

        with open(out_path, 'w') as fp:
            fp.write(SITEMAP_HEADER)
            self._writeManualLocs(sitemap, fp)
            self._writeAutoLocs(sitemap, fp)
            fp.write(SITEMAP_FOOTER)

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

        for name in source_names:
            logger.debug("Generating automatic sitemap entries for '%s'." %
                    name)
            source = self.app.getSource(name)
            if source is None:
                raise Exception("No such source: %s" % name)

            for page in source.getPages():
                route = self.app.getRoute(source.name, page.source_metadata)
                uri = route.getUri(page.source_metadata, provider=page)

                t = page.datetime.timestamp()
                sm_cfg = page.config.get('sitemap')

                args = {'url': uri, 'lastmod': strftime_iso8601(t)}
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

