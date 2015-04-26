import os
import os.path
import re
import glob
import logging
import datetime
from piecrust.sources.base import (
        PageSource, InvalidFileSystemEndpointError, PageFactory,
        MODE_CREATING, MODE_PARSING)
from piecrust.sources.interfaces import IPreparingSource
from piecrust.sources.mixins import SimplePaginationSourceMixin
from piecrust.sources.pageref import PageNotFoundError


logger = logging.getLogger(__name__)


class PostsSource(PageSource, IPreparingSource, SimplePaginationSourceMixin):
    PATH_FORMAT = None

    def __init__(self, app, name, config):
        super(PostsSource, self).__init__(app, name, config)
        self.fs_endpoint = config.get('fs_endpoint', name)
        self.fs_endpoint_path = os.path.join(self.root_dir, self.fs_endpoint)
        self.supported_extensions = list(app.config.get('site/auto_formats').keys())
        self.default_auto_format = app.config.get('site/default_auto_format')

    @property
    def path_format(self):
        return self.__class__.PATH_FORMAT

    def resolveRef(self, ref_path):
        path = os.path.normpath(os.path.join(self.fs_endpoint_path, ref_path))
        metadata = self._parseMetadataFromPath(ref_path)
        return path, metadata

    def findPageFactory(self, metadata, mode):
        year = metadata.get('year')
        month = metadata.get('month')
        day = metadata.get('day')
        slug = metadata.get('slug')

        try:
            if year is not None:
                year = int(year)
            if month is not None:
                month = int(month)
            if day is not None:
                day = int(day)
        except ValueError:
            return None

        ext = metadata.get('ext')
        if ext is None:
            if len(self.supported_extensions) == 1:
                ext = self.supported_extensions[0]
            elif mode == MODE_CREATING and self.default_auto_format:
                ext = self.default_auto_format

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
            if mode == MODE_CREATING:
                raise ValueError("Not enough information to find a post path.")
            possible_paths = glob.glob(path)
            if len(possible_paths) != 1:
                raise PageNotFoundError()
            path = possible_paths[0]
        elif mode == MODE_PARSING and not os.path.isfile(path):
            raise PageNotFoundError(path)

        rel_path = os.path.relpath(path, self.fs_endpoint_path)
        rel_path = rel_path.replace('\\', '/')
        fac_metadata = self._parseMetadataFromPath(rel_path)
        return PageFactory(self, rel_path, fac_metadata)

    def setupPrepareParser(self, parser, app):
        parser.add_argument('-d', '--date', help="The date of the post, "
                "in `year/month/day` format (defaults to today).")
        parser.add_argument('slug', help="The URL slug for the new post.")

    def buildMetadata(self, args):
        dt = datetime.date.today()
        if args.date:
            if args.date == 'today':
                pass # Keep the default we had.
            elif args.date == 'tomorrow':
                dt += datetime.timedelta(days=1)
            elif args.date.startswith('+'):
                try:
                    dt += datetime.timedelta(days=int(args.date.lstrip('+')))
                except ValueError:
                    raise Exception("Date offsets must be numbers.")
            else:
                try:
                    year, month, day = [int(s) for s in args.date.split('/')]
                except ValueError:
                    raise Exception("Dates must be of the form: YEAR/MONTH/DAY.")
                dt = datetime.date(year, month, day)

        year, month, day = dt.year, dt.month, dt.day
        return {'year': year, 'month': month, 'day': day, 'slug': args.slug}

    def _checkFsEndpointPath(self):
        if not os.path.isdir(self.fs_endpoint_path):
            if self.ignore_missing_dir:
                return False
            raise InvalidFileSystemEndpointError(self.name, self.fs_endpoint_path)
        return True

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
                'year': year,
                'month': month,
                'day': day,
                'slug': m.group('slug'),
                'date': timestamp
                }
        return metadata

    def _makeFactory(self, path, slug, year, month, day):
        path = path.replace('\\', '/')
        timestamp = datetime.date(year, month, day)
        metadata = {
                'slug': slug,
                'year': year,
                'month': month,
                'day': day,
                'date': timestamp}
        return PageFactory(self, path, metadata)


class FlatPostsSource(PostsSource):
    SOURCE_NAME = 'posts/flat'
    PATH_FORMAT = '%(year)s-%(month)s-%(day)s_%(slug)s.%(ext)s'

    def __init__(self, app, name, config):
        super(FlatPostsSource, self).__init__(app, name, config)

    def buildPageFactories(self):
        if not self._checkFsEndpointPath():
            return
        logger.debug("Scanning for posts (flat) in: %s" % self.fs_endpoint_path)
        pattern = re.compile(r'(\d{4})-(\d{2})-(\d{2})_(.*)\.(\w+)$')
        _, __, filenames = next(os.walk(self.fs_endpoint_path))
        for f in filenames:
            match = pattern.match(f)
            if match is None:
                name, ext = os.path.splitext(f)
                logger.warning("'%s' is not formatted as 'YYYY-MM-DD_slug-title.%s' "
                        "and will be ignored. Is that a typo?" % (f, ext))
                continue
            yield self._makeFactory(
                    f,
                    match.group(4),
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)))


class ShallowPostsSource(PostsSource):
    SOURCE_NAME = 'posts/shallow'
    PATH_FORMAT = '%(year)s/%(month)s-%(day)s_%(slug)s.%(ext)s'

    def __init__(self, app, name, config):
        super(ShallowPostsSource, self).__init__(app, name, config)

    def buildPageFactories(self):
        if not self._checkFsEndpointPath():
            return
        logger.debug("Scanning for posts (shallow) in: %s" % self.fs_endpoint_path)
        year_pattern = re.compile(r'(\d{4})$')
        file_pattern = re.compile(r'(\d{2})-(\d{2})_(.*)\.(\w+)$')
        _, year_dirs, __ = next(os.walk(self.fs_endpoint_path))
        year_dirs = [d for d in year_dirs if year_pattern.match(d)]
        for yd in year_dirs:
            if year_pattern.match(yd) is None:
                logger.warning("'%s' is not formatted as 'YYYY' and will be ignored. "
                        "Is that a typo?")
                continue
            year = int(yd)
            year_dir = os.path.join(self.fs_endpoint_path, yd)

            _, __, filenames = next(os.walk(year_dir))
            for f in filenames:
                match = file_pattern.match(f)
                if match is None:
                    name, ext = os.path.splitext(f)
                    logger.warning("'%s' is not formatted as 'MM-DD_slug-title.%s' "
                            "and will be ignored. Is that a typo?" % (f, ext))
                    continue
                yield self._makeFactory(
                        os.path.join(yd, f),
                        match.group(3),
                        year,
                        int(match.group(1)),
                        int(match.group(2)))


class HierarchyPostsSource(PostsSource):
    SOURCE_NAME = 'posts/hierarchy'
    PATH_FORMAT = '%(year)s/%(month)s/%(day)s_%(slug)s.%(ext)s'

    def __init__(self, app, name, config):
        super(HierarchyPostsSource, self).__init__(app, name, config)

    def buildPageFactories(self):
        if not self._checkFsEndpointPath():
            return
        logger.debug("Scanning for posts (hierarchy) in: %s" % self.fs_endpoint_path)
        year_pattern = re.compile(r'(\d{4})$')
        month_pattern = re.compile(r'(\d{2})$')
        file_pattern = re.compile(r'(\d{2})_(.*)\.(\w+)$')
        _, year_dirs, __ = next(os.walk(self.fs_endpoint_path))
        year_dirs = [d for d in year_dirs if year_pattern.match(d)]
        for yd in year_dirs:
            year = int(yd)
            year_dir = os.path.join(self.fs_endpoint_path, yd)

            _, month_dirs, __ = next(os.walk(year_dir))
            month_dirs = [d for d in month_dirs if month_pattern.match(d)]
            for md in month_dirs:
                month = int(md)
                month_dir = os.path.join(year_dir, md)

                _, __, filenames = next(os.walk(month_dir))
                for f in filenames:
                    match = file_pattern.match(f)
                    if match is None:
                        name, ext = os.path.splitext(f)
                        logger.warning("'%s' is not formatted as 'DD_slug-title.%s' "
                                "and will be ignored. Is that a typo?" % (f, ext))
                        continue
                    rel_name = os.path.join(yd, md, f)
                    yield self._makeFactory(
                            rel_name,
                            match.group(2),
                            year,
                            month,
                            int(match.group(1)))

