import sys
import os.path
import yaml
from piecrust import CONFIG_PATH, THEMES_DIR


class Theme(object):
    def getPath(self):
        mod_name = type(self).__module__
        mod_file = sys.modules[mod_name].__file__
        return os.path.dirname(mod_file)


class ThemeNotFoundError(Exception):
    pass


class ThemeLoader(object):
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def getThemeDir(self):
        # Pre-load the config quickly to see if we're loading a specific
        # theme from somehwere.
        # TODO: make configs and themes load together to speed this up.
        config_path = os.path.join(self.root_dir, CONFIG_PATH)
        with open(config_path, 'r', encoding='utf8') as fp:
            config = yaml.load(fp.read())
        if not config:
            return None
        site_config = config.get('site', {})
        theme = site_config.get('theme', None)
        if theme is None:
            return None

        # Get the list of directories in which themes are installed.
        dirs = []
        themes_dirs = site_config.get('themes_dirs', [])
        if isinstance(themes_dirs, str):
            dirs.append(os.path.join(self.root_dir,
                                     os.path.expanduser(themes_dirs)))
        else:
            dirs += [os.path.join(self.root_dir, os.path.expanduser(p))
                     for p in themes_dirs]

        # Add the default `themes` directory.
        default_themes_dir = os.path.join(self.root_dir, THEMES_DIR)
        if os.path.isdir(default_themes_dir):
            dirs.append(default_themes_dir)

        # Try to find the theme the user wants.
        for d in dirs:
            theme_dir = os.path.join(d, theme)
            if os.path.isdir(theme_dir):
                return theme_dir

        raise ThemeNotFoundError(
            "Can't find theme '%s'. Looked in: %s" %
            (theme, ', '.join(dirs)))

