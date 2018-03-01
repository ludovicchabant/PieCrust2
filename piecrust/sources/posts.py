import os
import os.path
import re
import logging
import datetime
from piecrust import osutil
from piecrust.routing import RouteParameter
from piecrust.sources.base import REL_PARENT_GROUP, REL_ASSETS, ContentItem
from piecrust.sources.fs import (
    FSContentSource, InvalidFileSystemEndpointError)
from piecrust.sources.interfaces import (
    IPreparingSource, IInteractiveSource, InteractiveField)
from piecrust.sources.mixins import SimpleAssetsSubDirMixin
from piecrust.uriutil import uri_to_title


logger = logging.getLogger(__name__)


class PostsSource(FSContentSource,
                  SimpleAssetsSubDirMixin,
                  IPreparingSource, IInteractiveSource):
    PATH_FORMAT = None
    DEFAULT_PIPELINE_NAME = 'page'

    def __init__(self, app, name, config):
        super().__init__(app, name, config)

        config.setdefault('data_type', 'page_iterator')

        self.auto_formats = app.config.get('site/auto_formats')
        self.default_auto_format = app.config.get('site/default_auto_format')
        self.supported_extensions = list(self.auto_formats)

    @property
    def path_format(self):
        return self.__class__.PATH_FORMAT

    def _finalizeContent(self, groups):
        SimpleAssetsSubDirMixin._removeAssetGroups(self, groups)

    def getRelatedContents(self, item, relationship):
        if relationship == REL_PARENT_GROUP:
            # Logically speaking, all posts are always flattened.
            return None

        if relationship == REL_ASSETS:
            return SimpleAssetsSubDirMixin._getRelatedAssetsContents(
                self, item)

        return FSContentSource.getRelatedContents(self, item, relationship)

    def findContentFromSpec(self, spec):
        metadata = self._parseMetadataFromPath(spec)
        return ContentItem(spec, metadata)

    def findContentFromRoute(self, route_params):
        year = route_params.get('year')
        month = route_params.get('month')
        day = route_params.get('day')
        slug = route_params.get('slug')

        try:
            if year is not None:
                year = int(year)
            if month is not None:
                month = int(month)
            if day is not None:
                day = int(day)
        except ValueError:
            return None

        ext = route_params.get('ext')
        if ext is None:
            if len(self.supported_extensions) == 1:
                ext = self.supported_extensions[0]

        replacements = {
            'year': '%04d' % year if year is not None else None,
            'month': '%02d' % month if month is not None else None,
            'day': '%02d' % day if day is not None else None,
            'slug': slug,
            'ext': ext
        }
        needs_recapture = False
        if year is None:
            needs_recapture = True
            replacements['year'] = '????'
        if month is None:
            needs_recapture = True
            replacements['month'] = '??'
        if day is None:
            needs_recapture = True
            replacements['day'] = '??'
        if slug is None:
            needs_recapture = True
            replacements['slug'] = '*'
        if ext is None:
            needs_recapture = True
            replacements['ext'] = '*'
        path = os.path.normpath(os.path.join(
            self.fs_endpoint_path, self.path_format % replacements))

        if needs_recapture:
            possible_paths = osutil.glob(path)
            if len(possible_paths) != 1:
                return None
            path = possible_paths[0]
        elif not os.path.isfile(path):
            return None

        metadata = self._parseMetadataFromPath(path)
        return ContentItem(path, metadata)

    def _parseMetadataFromPath(self, path):
        regex_repl = {
            'year': '(?P<year>\d{4})',
            'month': '(?P<month>\d{2})',
            'day': '(?P<day>\d{2})',
            'slug': '(?P<slug>.*)',
            'ext': '(?P<ext>.*)'
        }
        path_format_re = re.sub(r'([\-\.])', r'\\\1', self.path_format)
        pattern = path_format_re % regex_repl + '$'
        m = re.search(pattern, path.replace('\\', '/'))
        if not m:
            raise Exception("Expected to be able to match path with path "
                            "format: %s" % path)

        year = int(m.group('year'))
        month = int(m.group('month'))
        day = int(m.group('day'))
        timestamp = datetime.date(year, month, day)
        metadata = {
            'route_params': {
                'year': year,
                'month': month,
                'day': day,
                'slug': m.group('slug')
            },
            'date': timestamp
        }
        return metadata

    def getSupportedRouteParameters(self):
        return [
            RouteParameter('slug', RouteParameter.TYPE_STRING),
            RouteParameter('day', RouteParameter.TYPE_INT2),
            RouteParameter('month', RouteParameter.TYPE_INT2),
            RouteParameter('year', RouteParameter.TYPE_INT4)]

    def setupPrepareParser(self, parser, app):
        parser.add_argument(
            '-d', '--date',
            default='today',
            help=("The date of the post, in `year/month/day` format "
                  "(defaults to today)."))
        parser.add_argument('slug', help="The URL slug for the new post.")

    def createContent(self, args):
        dt = datetime.date.today()
        date = args.get('date')
        if isinstance(date, str):
            if date == 'today':
                pass  # Keep the default we had.
            elif date == 'tomorrow':
                dt += datetime.timedelta(days=1)
            elif date.startswith('+'):
                try:
                    dt += datetime.timedelta(days=int(date.lstrip('+')))
                except ValueError:
                    raise Exception("Date offsets must be numbers.")
            else:
                try:
                    year, month, day = [int(s) for s in date.split('/')]
                except ValueError:
                    raise Exception(
                        "Dates must be of the form 'YEAR/MONTH/DAY', "
                        "got '%s'." %
                        str(date))
                dt = datetime.date(year, month, day)
        elif isinstance(date, datetime.datetime):
            dt = datetime.date(date.year, date.month, date.day)
        else:
            try:
                dt = datetime.date(
                    int(args.get('year')),
                    int(args.get('month')),
                    int(args.get('day')))
            except ValueError:
                raise Exception("Incorrect year/month/day values: %s" %
                                args)

        slug = args.get('slug')
        if slug is None:
            raise Exception("No slug in args: %s" % args)
        slug, ext = os.path.splitext(slug)
        if not ext:
            ext = self.default_auto_format
        year, month, day = dt.year, dt.month, dt.day
        tokens = {
            'slug': args.get('slug'),
            'ext': ext,
            'year': '%04d' % year,
            'month': '%02d' % month,
            'day': '%02d' % day
        }
        rel_path = self.path_format % tokens
        path = os.path.join(self.fs_endpoint_path, rel_path)
        metadata = self._parseMetadataFromPath(path)
        metadata['config'] = {'title': uri_to_title(slug)}
        return ContentItem(path, metadata)

    def getInteractiveFields(self):
        dt = datetime.date.today()
        return [
            InteractiveField('year', InteractiveField.TYPE_INT, dt.year),
            InteractiveField('month', InteractiveField.TYPE_INT, dt.month),
            InteractiveField('day', InteractiveField.TYPE_INT, dt.day),
            InteractiveField('slug', InteractiveField.TYPE_STRING, 'new-post')]

    def _checkFsEndpointPath(self):
        if not os.path.isdir(self.fs_endpoint_path):
            if self.ignore_missing_dir:
                return False
            raise InvalidFileSystemEndpointError(self.name,
                                                 self.fs_endpoint_path)
        return True

    def _makeContentItem(self, rel_path, slug, year, month, day):
        path = os.path.join(self.fs_endpoint_path, rel_path)
        timestamp = datetime.date(year, month, day)
        metadata = {
            'route_params': {
                'slug': slug,
                'year': year,
                'month': month,
                'day': day},
            'date': timestamp
        }

        _, ext = os.path.splitext(path)
        if ext:
            fmt = self.auto_formats.get(ext.lstrip('.'))
            if fmt:
                metadata['config'] = {'format': fmt}

        return ContentItem(path, metadata)


class FlatPostsSource(PostsSource):
    SOURCE_NAME = 'posts/flat'
    PATH_FORMAT = '%(year)s-%(month)s-%(day)s_%(slug)s.%(ext)s'
    PATTERN = re.compile(r'(\d{4})-(\d{2})-(\d{2})_(.*)\.(\w+)$')

    def __init__(self, app, name, config):
        super().__init__(app, name, config)

    def getContents(self, group):
        if not self._checkFSEndpoint():
            return None

        logger.debug("Scanning for posts (flat) in: %s" %
                     self.fs_endpoint_path)
        pattern = FlatPostsSource.PATTERN
        _, __, filenames = next(osutil.walk(self.fs_endpoint_path))
        for f in filenames:
            match = pattern.match(f)
            if match is None:
                name, ext = os.path.splitext(f)
                logger.warning(
                    "'%s' is not formatted as 'YYYY-MM-DD_slug-title.%s' "
                    "and will be ignored. Is that a typo?" % (f, ext))
                continue
            yield self._makeContentItem(
                f,
                match.group(4),
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)))


class ShallowPostsSource(PostsSource):
    SOURCE_NAME = 'posts/shallow'
    PATH_FORMAT = '%(year)s/%(month)s-%(day)s_%(slug)s.%(ext)s'
    YEAR_PATTERN = re.compile(r'(\d{4})$')
    FILE_PATTERN = re.compile(r'(\d{2})-(\d{2})_(.*)\.(\w+)$')

    def __init__(self, app, name, config):
        super(ShallowPostsSource, self).__init__(app, name, config)

    def getContents(self, group):
        if not self._checkFsEndpointPath():
            return

        logger.debug("Scanning for posts (shallow) in: %s" %
                     self.fs_endpoint_path)
        year_pattern = ShallowPostsSource.YEAR_PATTERN
        file_pattern = ShallowPostsSource.FILE_PATTERN
        _, year_dirs, __ = next(osutil.walk(self.fs_endpoint_path))
        year_dirs = [d for d in year_dirs if year_pattern.match(d)]
        for yd in year_dirs:
            if year_pattern.match(yd) is None:
                logger.warning(
                    "'%s' is not formatted as 'YYYY' and will be ignored. "
                    "Is that a typo?")
                continue
            year = int(yd)
            year_dir = os.path.join(self.fs_endpoint_path, yd)

            _, __, filenames = next(osutil.walk(year_dir))
            for f in filenames:
                match = file_pattern.match(f)
                if match is None:
                    name, ext = os.path.splitext(f)
                    logger.warning(
                        "'%s' is not formatted as 'MM-DD_slug-title.%s' "
                        "and will be ignored. Is that a typo?" % (f, ext))
                    continue
                yield self._makeContentItem(
                    os.path.join(yd, f),
                    match.group(3),
                    year,
                    int(match.group(1)),
                    int(match.group(2)))


class HierarchyPostsSource(PostsSource):
    SOURCE_NAME = 'posts/hierarchy'
    PATH_FORMAT = '%(year)s/%(month)s/%(day)s_%(slug)s.%(ext)s'
    YEAR_PATTERN = re.compile(r'(\d{4})$')
    MONTH_PATTERN = re.compile(r'(\d{2})$')
    FILE_PATTERN = re.compile(r'(\d{2})_(.*)\.(\w+)$')

    def __init__(self, app, name, config):
        super(HierarchyPostsSource, self).__init__(app, name, config)

    def getContents(self, group):
        if not self._checkFsEndpointPath():
            return

        logger.debug("Scanning for posts (hierarchy) in: %s" %
                     self.fs_endpoint_path)
        year_pattern = HierarchyPostsSource.YEAR_PATTERN
        month_pattern = HierarchyPostsSource.MONTH_PATTERN
        file_pattern = HierarchyPostsSource.FILE_PATTERN
        _, year_dirs, __ = next(osutil.walk(self.fs_endpoint_path))
        year_dirs = [d for d in year_dirs if year_pattern.match(d)]
        for yd in year_dirs:
            year = int(yd)
            year_dir = os.path.join(self.fs_endpoint_path, yd)

            _, month_dirs, __ = next(osutil.walk(year_dir))
            month_dirs = [d for d in month_dirs if month_pattern.match(d)]
            for md in month_dirs:
                month = int(md)
                month_dir = os.path.join(year_dir, md)

                _, __, filenames = next(osutil.walk(month_dir))
                for f in filenames:
                    match = file_pattern.match(f)
                    if match is None:
                        name, ext = os.path.splitext(f)
                        logger.warning(
                            "'%s' is not formatted as 'DD_slug-title.%s' "
                            "and will be ignored. Is that a typo?" % (f, ext))
                        continue
                    rel_name = os.path.join(yd, md, f)
                    yield self._makeContentItem(
                        rel_name,
                        match.group(2),
                        year,
                        month,
                        int(match.group(1)))

