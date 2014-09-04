import re
import os
import os.path
import logging
from werkzeug.utils import cached_property
from piecrust.configuration import ConfigurationError
from piecrust.data.base import IPaginationSource, PaginationData
from piecrust.data.filters import PaginationFilter
from piecrust.page import Page


REALM_USER = 0
REALM_THEME = 1
REALM_NAMES = {
        REALM_USER: 'User',
        REALM_THEME: 'Theme'}


MODE_PARSING = 0
MODE_CREATING = 1


logger = logging.getLogger(__name__)


page_ref_pattern = re.compile(r'(?P<src>[\w]+)\:(?P<path>.*?)(;|$)')


class PageNotFoundError(Exception):
    pass


class InvalidFileSystemEndpointError(Exception):
    def __init__(self, source_name, fs_endpoint):
        super(InvalidFileSystemEndpointError, self).__init__(
                "Invalid file-system endpoint for source '%s': %s" %
                (source_name, fs_endpoint))


class PageFactory(object):
    """ A class responsible for creating a page.
    """
    def __init__(self, source, rel_path, metadata):
        self.source = source
        self.rel_path = rel_path
        self.metadata = metadata

    @cached_property
    def ref_spec(self):
        return '%s:%s' % (self.source.name, self.rel_path)

    @cached_property
    def path(self):
        return self.source.resolveRef(self.rel_path)

    def buildPage(self):
        repo = self.source.app.env.page_repository
        if repo is not None:
            cache_key = '%s:%s' % (self.source.name, self.rel_path)
            return repo.get(cache_key, self._doBuildPage)
        return self._doBuildPage()

    def _doBuildPage(self):
        logger.debug("Building page: %s" % self.path)
        page = Page(self.source, self.metadata, self.rel_path)
        # Load it right away, especially when using the page repository,
        # because we'll be inside a critical scope.
        page._load()
        return page


class CachedPageFactory(object):
    """ A `PageFactory` (in appearance) that already has a page built.
    """
    def __init__(self, page):
        self._page = page

    @property
    def rel_path(self):
        return self._page.rel_path

    @property
    def metadata(self):
        return self._page.source_metadata

    @property
    def ref_spec(self):
        return self._page.ref_spec

    @property
    def path(self):
        return self._page.path

    def buildPage(self):
        return self._page


class PageRef(object):
    """ A reference to a page, with support for looking a page in different
        realms.
    """
    def __init__(self, app, page_ref):
        self.app = app
        self._page_ref = page_ref
        self._paths = None
        self._first_valid_path_index = -2
        self._exts = list(app.config.get('site/auto_formats').keys())

    @property
    def exists(self):
        try:
            self._checkPaths()
            return True
        except PageNotFoundError:
            return False

    @property
    def source_name(self):
        self._checkPaths()
        return self._paths[self._first_valid_path_index][0]

    @property
    def source(self):
        return self.app.getSource(self.source_name)

    @property
    def rel_path(self):
        self._checkPaths()
        return self._paths[self._first_valid_path_index][1]

    @property
    def path(self):
        self._checkPaths()
        return self._paths[self._first_valid_path_index][2]

    @property
    def possible_rel_paths(self):
        self._load()
        return [p[1] for p in self._paths]

    @property
    def possible_paths(self):
        self._load()
        return [p[2] for p in self._paths]

    def _load(self):
        if self._paths is not None:
            return

        it = list(page_ref_pattern.finditer(self._page_ref))
        if len(it) == 0:
            raise Exception("Invalid page ref: %s" % self._page_ref)

        self._paths = []
        for m in it:
            source_name = m.group('src')
            source = self.app.getSource(source_name)
            if source is None:
                raise Exception("No such source: %s" % source_name)
            rel_path = m.group('path')
            path = source.resolveRef(rel_path)
            if '%ext%' in rel_path:
                for e in self._exts:
                    self._paths.append((source_name,
                        rel_path.replace('%ext%', e),
                        path.replace('%ext%', e)))
            else:
                self._paths.append((source_name, rel_path, path))

    def _checkPaths(self):
        if self._first_valid_path_index >= 0:
            return
        if self._first_valid_path_index == -1:
            raise PageNotFoundError("No valid paths were found for page reference:" %
                    self._page_ref)

        self._load()
        for i, path_info in enumerate(self._paths):
            if os.path.isfile(path_info[2]):
                self._first_valid_path_index = i
                break


class PageSource(object):
    """ A source for pages, e.g. a directory with one file per page.
    """
    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.config = config
        self._factories = None
        self._provider_type = None

    def __getattr__(self, name):
        try:
            return self.config[name]
        except KeyError:
            raise AttributeError()

    @property
    def is_theme_source(self):
        return self.realm == REALM_THEME

    @property
    def root_dir(self):
        if self.is_theme_source:
            return self.app.theme_dir
        return self.app.root_dir

    def getPageFactories(self):
        if self._factories is None:
            self._factories = list(self.buildPageFactories())
        return self._factories

    def buildPageFactories(self):
        raise NotImplementedError()

    def resolveRef(self, ref_path):
        raise NotImplementedError()

    def findPagePath(self, metadata, mode):
        raise NotImplementedError()

    def buildDataProvider(self, page, user_data):
        if self._provider_type is None:
            cls = next((pt for pt in self.app.plugin_loader.getDataProviders()
                    if pt.PROVIDER_NAME == self.data_type),
                    None)
            if cls is None:
                raise ConfigurationError("Unknown data provider type: %s" %
                        self.data_type)
            self._provider_type = cls

        return self._provider_type(self, page, user_data)

    def getTaxonomyPageRef(self, tax_name):
        tax_pages = self.config.get('taxonomy_pages')
        if tax_pages is None:
            return None
        return tax_pages.get(tax_name)


class IPreparingSource:
    def setupPrepareParser(self, parser, app):
        raise NotImplementedError()

    def buildMetadata(self, args):
        raise NotImplementedError()


class SimplePaginationSourceMixin(IPaginationSource):
    def getItemsPerPage(self):
        return self.config['items_per_page']

    def getSourceIterator(self):
        return SourceFactoryIterator(self)

    def getSorterIterator(self, it):
        return DateSortIterator(it)

    def getTailIterator(self, it):
        return PaginationDataBuilderIterator(it)

    def getPaginationFilter(self, page):
        conf = (page.config.get('items_filters') or
                page.app.config.get('site/items_filters'))
        if conf == 'none' or conf == 'nil' or conf == '':
            conf = None
        if conf is not None:
            f = PaginationFilter()
            f.addClausesFromConfig(conf)
            return f
        return None


class ArraySource(PageSource, SimplePaginationSourceMixin):
    def __init__(self, app, inner_source, name='array', config=None):
        super(ArraySource, self).__init__(app, name, config or {})
        self.inner_source = inner_source

    @property
    def page_count(self):
        return len(self.inner_source)

    def getPageFactories(self):
        for p in self.inner_source:
            yield CachedPageFactory(p)


class SimplePageSource(PageSource):
    def __init__(self, app, name, config):
        super(SimplePageSource, self).__init__(app, name, config)
        self.fs_endpoint = config.get('fs_endpoint', name)
        self.fs_endpoint_path = os.path.join(self.root_dir, self.fs_endpoint)
        self.supported_extensions = list(app.config.get('site/auto_formats').keys())
        self.default_auto_format = app.config.get('site/default_auto_format')

    def buildPageFactories(self):
        logger.debug("Scanning for pages in: %s" % self.fs_endpoint_path)
        if not os.path.isdir(self.fs_endpoint_path):
            if self.ignore_missing_dir:
                return
            raise InvalidFileSystemEndpointError(self.name, self.fs_endpoint_path)

        for dirpath, dirnames, filenames in os.walk(self.fs_endpoint_path):
            rel_dirpath = os.path.relpath(dirpath, self.fs_endpoint_path)
            dirnames[:] = list(filter(self._filterPageDirname, dirnames))
            for f in filter(self._filterPageFilename, filenames):
                slug, ext = os.path.splitext(os.path.join(rel_dirpath, f))
                slug = slug.replace('\\', '/')
                if ext.lstrip('.') not in self.supported_extensions:
                    slug += ext
                if slug.startswith('./') or slug.startswith('.\\'):
                    slug = slug[2:]
                if slug == '_index':
                    slug = ''
                metadata = {'path': slug}
                fac_path = f
                if rel_dirpath != '.':
                    fac_path = os.path.join(rel_dirpath, f)
                fac_path = fac_path.replace('\\', '/')
                yield PageFactory(self, fac_path, metadata)

    def resolveRef(self, ref_path):
        return os.path.normpath(
                os.path.join(self.fs_endpoint_path, ref_path))

    def findPagePath(self, metadata, mode):
        uri_path = metadata['path']
        if uri_path == '':
            uri_path = '_index'
        path = os.path.normpath(os.path.join(self.fs_endpoint_path, uri_path))
        _, ext = os.path.splitext(path)

        if mode == MODE_CREATING:
            if ext == '':
                path = '%s.%s' % (path, self.default_auto_format)
            rel_path = os.path.relpath(path, self.fs_endpoint_path)
            rel_path = rel_path.replace('\\', '/')
            return rel_path, metadata

        if ext == '':
            paths_to_check = ['%s.%s' % (path, e)
                    for e in self.supported_extensions]
        else:
            paths_to_check = [path]
        for path in paths_to_check:
            if os.path.isfile(path):
                rel_path = os.path.relpath(path, self.fs_endpoint_path)
                rel_path = rel_path.replace('\\', '/')
                return rel_path, metadata

        return None, None

    def _filterPageDirname(self, d):
        return not d.endswith('-assets')

    def _filterPageFilename(self, f):
        name, ext = os.path.splitext(f)
        return (f[0] != '.' and   # .DS_store and other crap
                f[-1] != '~' and  # Vim temp files and what-not
                f not in ['Thumbs.db']) # Windows bullshit


class DefaultPageSource(SimplePageSource, IPreparingSource,
        SimplePaginationSourceMixin):
    SOURCE_NAME = 'default'

    def __init__(self, app, name, config):
        super(DefaultPageSource, self).__init__(app, name, config)

    def setupPrepareParser(self, parser, app):
        parser.add_argument('uri', help='The URI for the new page.')

    def buildMetadata(self, args):
        return {'path': args.uri}


class SourceFactoryIterator(object):
    def __init__(self, source):
        self.source = source
        self.it = None # This is to permit recursive traversal of the
                       # iterator chain. It acts as the end.

    def __iter__(self):
        for factory in self.source.getPageFactories():
            yield factory.buildPage()


class DateSortIterator(object):
    def __init__(self, it, reverse=True):
        self.it = it
        self.reverse = reverse

    def __iter__(self):
        return iter(sorted(self.it,
                           key=lambda x: x.datetime, reverse=self.reverse))


class PaginationDataBuilderIterator(object):
    def __init__(self, it):
        self.it = it

    def __iter__(self):
        for page in self.it:
            if page is None:
                yield None
            else:
                yield PaginationData(page)

