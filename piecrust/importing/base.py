import os.path
import codecs
import logging
import yaml
from piecrust.pathutil import SiteNotFoundError, multi_fnmatch_filter


logger = logging.getLogger(__name__)


class Importer(object):
    def __init__(self):
        self.name = None
        self.description = None
        self.requires_website = True

    def setupParser(self, parser, app):
        raise NotImplementedError()

    def importWebsite(self, app, args):
        raise NotImplementedError()

    def checkedImportWebsite(self, ctx):
        if ctx.app.root_dir is None and self.requires_website:
            raise SiteNotFoundError()
        self.importWebsite(ctx.app, ctx.args)
        return 0


class FileWalkingImporter(Importer):
    def setupParser(self, parser, app):
        parser.add_argument('--exclude', nargs='+',
                help=("Patterns of files and directories to exclude "
                      "from the import (always includes `.git*`, "
                      "`.hg*`, `.svn`, `.bzr`)."))

    def _startWalk(self, root_dir, exclude, *args, **kwargs):
        if exclude is None:
            exclude = []
        exclude += ['.git*', '.hg*', '.svn', '.bzr']

        for dirpath, dirnames, filenames in os.walk(root_dir):
            rel_dirpath = os.path.relpath(dirpath, root_dir)
            if rel_dirpath == '.':
                rel_dirpath = ''

            dirnames[:] = multi_fnmatch_filter(
                    dirnames, exclude,
                    modifier=lambda d: os.path.join(rel_dirpath, d),
                    inverse=True)
            filenames = multi_fnmatch_filter(
                    filenames, exclude,
                    modifier=lambda f: os.path.join(rel_dirpath, f),
                    inverse=True)

            for fn in filenames:
                full_fn = os.path.join(dirpath, fn)
                rel_fn = os.path.join(rel_dirpath, fn)
                self._importFile(full_fn, rel_fn, *args, **kwargs)


def create_page(app, endpoint_dir, slug, metadata, content):
    path = os.path.join(app.root_dir, endpoint_dir, slug)
    logging.debug("Creating page: %s" % os.path.relpath(path, app.root_dir))
    header = yaml.dump(metadata)
    os.makedirs(os.path.dirname(path), 0o755, True)
    with codecs.open(path, 'w', encoding='utf8') as fp:
        fp.write("---\n")
        fp.write(header)
        fp.write("---\n")
        fp.write(content)

