import os
import os.path
import logging
from piecrust import THEME_DIR, THEME_CONFIG_PATH, THEME_INFO_PATH
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class ThemesCommand(ChefCommand):
    def __init__(self):
        super(ThemesCommand, self).__init__()
        self.name = 'themes'
        self.description = "Manage the themes for the current website."

    def setupParser(self, parser, app):
        subparsers = parser.add_subparsers()
        p = subparsers.add_parser(
            'info',
            help="Provides information about the current theme.")
        p.set_defaults(sub_func=self._info)

        p = subparsers.add_parser(
            'override',
            help="Copies the current theme to the website for "
            "customization.")
        p.set_defaults(sub_func=self._overrideTheme)

        p = subparsers.add_parser(
            'link',
            help="Makes a given theme the active one for the current "
            "website by creating a symbolic link to it from the "
            "'theme' directory.")
        p.add_argument(
            'theme_dir',
            help="The directory of the theme to link.")
        p.set_defaults(sub_func=self._linkTheme)

        p = subparsers.add_parser(
            'unlink',
            help="Removes the currently active theme for the website. "
            "This removes the symbolic link to the theme, if any, or "
            "deletes the theme folder if it was copied locally.")
        p.set_defaults(sub_func=self._unlinkTheme)

    def checkedRun(self, ctx):
        from piecrust.pathutil import SiteNotFoundError

        if ctx.app.root_dir is None:
            raise SiteNotFoundError(theme=ctx.app.theme_site)

        if not hasattr(ctx.args, 'sub_func'):
            ctx.parser.parse_args(['themes', '--help'])
            return
        ctx.args.sub_func(ctx)

    def _info(self, ctx):
        import yaml

        theme_dir = ctx.app.theme_dir
        if not os.path.exists(theme_dir):
            logger.info("Using default theme, from: %s" % ctx.app.theme_dir)
        elif theme_dir.startswith(ctx.app.root_dir):
            if os.path.islink(theme_dir):
                target = os.readlink(theme_dir)
                target = os.path.join(os.path.dirname(theme_dir), target)
                logger.info("Using local theme, from: %s" % target)
            else:
                logger.info("Using local theme.")
        else:
            logger.info("Using theme from: %s" % theme_dir)

        info_path = os.path.join(theme_dir, THEME_CONFIG_PATH)
        if os.path.exists(info_path):
            info = None
            with open(info_path, 'r', encoding='utf8') as fp:
                theme_cfg = yaml.load(fp.read())
                if isinstance(theme_cfg, dict):
                    info = theme_cfg.get('theme')
            if info:
                logger.info("Theme info:")
                for k, v in info.items():
                    logger.info("  - %s: %s" % (str(k), str(v)))

    def _overrideTheme(self, ctx):
        import shutil

        theme_dir = ctx.app.theme_dir
        if not theme_dir:
            logger.error("There is no theme currently applied.")
            return 1

        copies = []
        app_dir = ctx.app.root_dir
        for dirpath, dirnames, filenames in os.walk(theme_dir):
            rel_dirpath = os.path.relpath(dirpath, theme_dir)
            for name in filenames:
                if (dirpath == theme_dir and
                        name in [THEME_CONFIG_PATH, THEME_INFO_PATH]):
                    continue
                src_path = os.path.join(dirpath, name)
                dst_path = os.path.join(app_dir, rel_dirpath, name)
                copies.append((src_path, dst_path))

        conflicts = set()
        for c in copies:
            if os.path.exists(c[1]):
                conflicts.add(c[1])
        if conflicts:
            logger.warning("Some website files override theme files:")
            for c in conflicts:
                logger.warning(os.path.relpath(c, app_dir))
            logger.warning("")
            logger.warning("The local website files will be preserved, and "
                           "the conflicting theme files won't be copied "
                           "locally.")

        for c in copies:
            if not c[1] in conflicts:
                logger.info(os.path.relpath(c[1], app_dir))
                os.makedirs(os.path.dirname(c[1]), exist_ok=True)
                shutil.copy2(c[0], c[1])

    def _linkTheme(self, ctx):
        if not os.path.isdir(ctx.args.theme_dir):
            logger.error("Invalid theme directory: %s" % ctx.args.theme_dir)
            return 1

        msg = ("A theme already exists, and will be deleted. "
               "Are you sure? [Y/n]")
        self._doUnlinkTheme(ctx.app.root_dir, msg)

        theme_dir = os.path.join(ctx.app.root_dir, THEME_DIR)
        try:
            os.symlink(ctx.args.theme_dir, theme_dir)
        except (NotImplementedError, OSError) as ex:
            if ctx.args.link_only:
                logger.error("Couldn't symlink the theme: %s" % ex)
                return 1

    def _unlinkTheme(self, ctx):
        msg = ("The active theme is local. Are you sure you want "
               "to delete the theme directory? [Y/n]")
        self._doUnlinkTheme(ctx.app.root_dir, msg)

    def _doUnlinkTheme(self, root_dir, delete_message):
        import shutil

        theme_dir = os.path.join(root_dir, THEME_DIR)

        if os.path.islink(theme_dir):
            logger.debug("Unlinking: %s" % theme_dir)
            os.unlink(theme_dir)
            return True

        if os.path.isdir(theme_dir):
            logger.warning(delete_message)
            ans = input()
            if len(ans) > 0 and ans.lower() not in ['y', 'yes']:
                return 1

            logger.debug("Deleting: %s" % theme_dir)
            shutil.rmtree(theme_dir)

            return True

        return False

