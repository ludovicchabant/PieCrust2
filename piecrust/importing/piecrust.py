import os
import os.path
import re
import shutil
import logging
import yaml
from piecrust.importing.base import FileWalkingImporter


logger = logging.getLogger(__name__)


class PieCrust1Importer(FileWalkingImporter):
    name = 'piecrust1'
    description = "Imports content from a PieCrust 1 website."
    requires_website = False

    def setupParser(self, parser, app):
        super(PieCrust1Importer, self).setupParser(parser, app)
        parser.add_argument('root_dir', nargs='?',
                help="The root directory of the PieCrust 1 website.")
        parser.add_argument('--upgrade', action='store_true',
                help="Upgrade the current website in place.")

    def importWebsite(self, app, args):
        if args.root_dir and args.upgrade:
            raise Exception("Can't specifiy both a root directory and `--upgrade`.")
        if args.root_dir is None and not args.upgrade:
            raise Exception("Need to specify either a root directory or `--upgrade`.")

        if app.root_dir is None and not args.upgrade:
            raise Exception("Need to run the import from inside a PieCrust 2 "
                            "website. Use `--upgrade` to upgrade from inside "
                            "a PieCrust 1 website.")
        if app.root_dir is not None and args.upgrade:
            raise Exception("Already in a PieCrust 2 website. Specify the "
                            "PieCrust 1 website to import from.")

        src_root_dir = os.getcwd() if args.upgrade else args.root_dir
        out_root_dir = src_root_dir if args.upgrade else app.root_dir
        logger.debug("Importing PieCrust 1 site from: %s" % src_root_dir)
        exclude = args.exclude or []
        exclude += ['_cache', '_counter']
        self._startWalk(src_root_dir, exclude, out_root_dir, args.upgrade)
        if args.upgrade:
            self._cleanEmptyDirectories(src_root_dir)
        logger.info("The PieCrust website was successfully imported.")

    def _importFile(self, full_fn, rel_fn, out_root_dir, is_move):
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
        full_dest_path = os.path.join(out_root_dir, dest_path)
        os.makedirs(os.path.dirname(full_dest_path), 0o755, True)
        if convert_func is None:
            if is_move:
                shutil.move(full_fn, full_dest_path)
            else:
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
            if is_move:
                os.remove(full_fn)

    def _cleanEmptyDirectories(self, root_dir):
        for item in os.listdir(root_dir):
            if not os.path.isdir(item):
                continue

            file_count = 0
            item_path = os.path.join(root_dir, item)
            for _, __, filenames in os.walk(item_path):
                file_count += len(filenames)
            if file_count == 0:
                logger.debug("Deleting empty directory: %s" % item)
                shutil.rmtree(item_path)

    def convertConfig(self, content):
        config = yaml.load(content)
        sitec = config.setdefault('site', {})
        if 'templates_dirs' in sitec:
            tdc = sitec['templates_dirs']
            cl = len('_content/')
            if isinstance(tdc, str) and re.match(r'^_content[/\\]', tdc):
                sitec['templates_dirs'] = tdc[cl:]
            elif isinstance(tdc, list):
                sitec['templates_dirs'] = list(map(
                    lambda d: d[cl:] if re.match(r'^_content[/\\]', d) else d,
                    tdc))

        jinjac = config.setdefault('jinja', {})
        jinjac['twig_compatibility'] = True

        if 'baker' in config:
            if 'skip_patterns' in config['baker']:
                config['baker']['ignore'] = config['baker']['skip_patterns']
                del config['baker']['skip_patterns']
            if 'force_patterns' in config['baker']:
                config['baker']['force'] = config['baker']['force_patterns']
                del config['baker']['force_patterns']

        content = yaml.dump(config, default_flow_style=False,
                            allow_unicode=True)
        return content

    def convertPage(self, content):
        return content

