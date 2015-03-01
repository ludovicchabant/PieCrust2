import os
import os.path
import shutil
import logging
import yaml
from piecrust import (
        RESOURCES_DIR, THEME_DIR, THEME_CONFIG_PATH, THEME_INFO_PATH)
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class ThemesCommand(ChefCommand):
    def __init__(self):
        super(ThemesCommand, self).__init__()
        self.name = 'themes'
        self.description = "Manage the themes for the current website."

    def setupParser(self, parser, app):
        if app.root_dir is None:
            return

        subparsers = parser.add_subparsers()
        p = subparsers.add_parser(
                'create',
                help="Create a new theme for the current website.")
        p.add_argument(
                '--from-default',
                action='store_true',
                help=("Create a new theme by copying the default PieCrust "
                      "theme into the theme directory"))
        p.add_argument(
                'theme_name',
                help=("The name of the theme"))
        p.set_defaults(sub_func=self._createTheme)

        p = subparsers.add_parser(
                'override',
                help="Copies a theme to the website for customization.")
        p.set_defaults(sub_func=self._overrideTheme)

    def checkedRun(self, ctx):
        ctx.args.sub_func(ctx)

    def _createTheme(self, ctx):
        theme_dir = os.path.join(ctx.app.root_dir, THEME_DIR)
        if os.path.exists(theme_dir):
            logger.warning("A theme already exists, and will be overwritten. "
                           "Are you sure? [Y/n]")
            ans = input()
            if len(ans) > 0 and ans.lower() not in ['y', 'yes']:
                return 1

            shutil.rmtree(theme_dir)

        try:
            if ctx.args.from_default:
                def reporting_copy2(src, dst):
                    rel_dst = os.path.relpath(dst, ctx.app.root_dir)
                    logger.info(rel_dst)
                    shutil.copy2(src, dst)

                default_theme_dir = os.path.join(RESOURCES_DIR, 'theme')
                shutil.copytree(default_theme_dir, theme_dir,
                                copy_function=reporting_copy2)
                return 0

            logger.info("Creating theme directory.")
            os.makedirs(theme_dir)

            logger.info("Creating theme_config.yml")
            config_path = os.path.join(theme_dir, THEME_CONFIG_PATH)
            with open(config_path, 'w', encoding='utf8') as fp:
                fp.write('')

            logger.info("Creating theme_info.yml")
            info_path = os.path.join(theme_dir, THEME_INFO_PATH)
            with open(info_path, 'w', encoding='utf8') as fp:
                yaml.dump(
                        {
                            'name': ctx.args.theme_name or 'My New Theme',
                            'description': "A new PieCrust theme.",
                            'authors': ['Your Name Here <email or twitter>'],
                            'url': 'http://www.example.org'},
                        fp,
                        default_flow_style=False)
            return 0
        except:
            logger.error("Error occured, deleting theme directory.")
            shutil.rmtree(theme_dir)
            raise

    def _overrideTheme(self, ctx):
        app_dir = ctx.app.root_dir
        theme_dir = ctx.app.theme_dir
        if not theme_dir:
            logger.error("There is not theme currently applied to override.")
            return 1

        copies = []
        for dirpath, dirnames, filenames in os.walk(theme_dir):
            rel_dirpath = os.path.relpath(dirpath, theme_dir)
            for name in filenames:
                if (dirpath == theme_dir and
                        name in [THEME_CONFIG_PATH, THEME_INFO_PATH]):
                    continue
                src_path = os.path.join(dirpath, name)
                dst_path = os.path.join(app_dir, rel_dirpath, name)
                copies.append((src_path, dst_path))

        conflicts = []
        for c in copies:
            if os.path.exists(c[1]):
                conflicts.append(c[1])
        if conflicts:
            logger.warning("Some website files will be overwritten:")
            for c in conflicts:
                logger.warning(os.path.relpath(c, app_dir))
            logger.warning("Are you sure? [Y/n]")
            ans = input()
            if len(ans) > 0 and ans.lower() not in ['y', 'yes']:
                return 1

        for c in copies:
            logger.info(os.path.relpath(c[1], app_dir))
            if not os.path.exists(os.path.dirname(c[1])):
                os.makedirs(os.path.dirname(c[1]))
            shutil.copy2(c[0], c[1])

