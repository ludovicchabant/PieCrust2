
CACHE_DIR = '_cache'
ASSETS_DIR = 'assets'
TEMPLATES_DIR = 'templates'
THEME_DIR = 'theme'

CONFIG_PATH = 'config.yml'
THEME_CONFIG_PATH = 'theme_config.yml'
THEME_INFO_PATH = 'theme_info.yml'

DEFAULT_FORMAT = 'markdown'
DEFAULT_TEMPLATE_ENGINE = 'jinja2'
DEFAULT_POSTS_FS = 'flat'
DEFAULT_DATE_FORMAT = '%b %d, %Y'
DEFAULT_THEME_SOURCE = 'http://bitbucket.org/ludovicchabant/'

PIECRUST_URL = 'http://bolt80.com/piecrust/'

try:
    from piecrust.__version__ import APP_VERSION
except ImportError:
    APP_VERSION = 'unknown'

import os.path
RESOURCES_DIR = os.path.join(os.path.dirname(__file__), 'resources')

