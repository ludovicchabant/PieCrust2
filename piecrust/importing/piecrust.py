import os
import os.path
import re
import shutil
import logging
from piecrust.importing.base import FileWalkingImporter


logger = logging.getLogger(__name__)


class PieCrust1Importer(FileWalkingImporter):
    def __init__(self):
        super(PieCrust1Importer, self).__init__()
        self.name = 'piecrust1'
        self.description = "Imports content from a PieCrust 1 website."

    def setupParser(self, parser, app):
        super(PieCrust1Importer, self).setupParser(parser, app)
        parser.add_argument('root_dir',
                help="The root directory of the PieCrust 1 website.")

    def importWebsite(self, app, args):
        logger.debug("Importing PieCrust 1 site from: %s" % args.root_dir)
        exclude = args.exclude or []
        exclude += ['_cache', '_counter']
        self._startWalk(args.root_dir, exclude, app)
        logger.info("The PieCrust website was successfully imported.")

    def _importFile(self, full_fn, rel_fn, app):
        logger.debug("- %s" % rel_fn)
        dest_path = rel_fn
        convert_func = None
        if rel_fn.replace('\\', '/') == '_content/config.yml':
            dest_path = 'config.yml'
            convert_func = self.convertConfig
        elif rel_fn.startswith('_content'):
            dest_path = rel_fn[len('_content/'):]
            fn_dirname = os.path.dirname(rel_fn)
            if not fn_dirname.endswith('-assets'):
                convert_func = self.convertPage
        else:
            dest_path = 'assets/' + rel_fn

        logger.debug("  %s -> %s" % (rel_fn, dest_path))
        full_dest_path = os.path.join(app.root_dir, dest_path)
        os.makedirs(os.path.dirname(full_dest_path), 0o755, True)
        if convert_func is None:
            shutil.copy2(full_fn, full_dest_path)
        else:
            with open(full_fn, 'r', encoding='utf8') as fp:
                content = fp.read()
            converted_content = convert_func(content)
            with open(full_dest_path, 'w', encoding='utf8') as fp:
                fp.write(converted_content)
            if converted_content != content:
                logger.warning("'%s' has been modified. The original version "
                               "has been kept for reference." % rel_fn)
                shutil.copy2(full_fn, full_dest_path + '.orig')

    def convertConfig(self, content):
        return content

    def convertPage(self, content):
        return content

