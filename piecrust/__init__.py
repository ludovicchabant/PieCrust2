
CACHE_DIR = '_cache'
ASSETS_DIR = 'assets'
TEMPLATES_DIR = 'templates'
THEME_DIR = 'theme'
THEMES_DIR = 'themes'
PLUGINS_DIR = 'plugins'

CONFIG_PATH = 'config.yml'
THEME_CONFIG_PATH = 'theme_config.yml'
THEME_INFO_PATH = 'theme_info.yml'
ASSET_DIR_SUFFIX = '-assets'

DEFAULT_FORMAT = 'markdown'
DEFAULT_TEMPLATE_ENGINE = 'jinja2'
DEFAULT_POSTS_FS = 'flat'
DEFAULT_DATE_FORMAT = '%b %d, %Y'
DEFAULT_THEME_SOURCE = 'https://bitbucket.org/ludovicchabant/'

PIECRUST_URL = 'https://bolt80.com/piecrust/'

CACHE_VERSION = 33

try:
    from piecrust.__version__ import APP_VERSION
except ImportError:
    APP_VERSION = 'unknown'

import os.path  # NOQA
RESOURCES_DIR = os.path.join(os.path.dirname(__file__), 'resources')

