import os.path
import codecs
import logging
import yaml
from piecrust.pathutil import SiteNotFoundError


logger = logging.getLogger(__name__)


class Importer(object):
    def __init__(self):
        self.name = None
        self.description = None

    def setupParser(self, parser, app):
        raise NotImplementedError()

    def importWebsite(self, app, args):
        raise NotImplementedError()

    def checkedImportWebsite(self, ctx):
        if ctx.app.root_dir is None:
            raise SiteNotFoundError()
        self.importWebsite(ctx.app, ctx.args)
        return 0


def create_page(app, endpoint_dir, slug, metadata, content):
    path = os.path.join(app.root_dir, endpoint_dir, slug)
    logging.debug("Creating page: %s" % os.path.relpath(path, app.root_dir))
    header = yaml.dump(metadata)
    os.makedirs(os.path.dirname(path), 0o755, True)
    with codecs.open(path, 'w', 'utf8') as fp:
        fp.write("---\n")
        fp.write(header)
        fp.write("---\n")
        fp.write(content)

