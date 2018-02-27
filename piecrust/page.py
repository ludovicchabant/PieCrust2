import re
import json
import hashlib
import logging
import datetime
import collections
from werkzeug.utils import cached_property
from piecrust.configuration import (
    Configuration, ConfigurationError,
    parse_config_header,
    MERGE_PREPEND_LISTS)


logger = logging.getLogger(__name__)


class PageConfiguration(Configuration):
    def __init__(self, values=None, validate=True):
        super(PageConfiguration, self).__init__(values, validate)

    def _validateAll(self, values):
        values.setdefault('content_type', 'html')
        ppp = values.get('posts_per_page')
        if ppp is not None:
            values.setdefault('items_per_page', ppp)
        pf = values.get('posts_filters')
        if pf is not None:
            values.setdefault('items_filters', pf)
        return values


FLAG_NONE = 0
FLAG_RAW_CACHE_VALID = 2**0


class PageNotFoundError(Exception):
    pass


class Page:
    """ Represents a page that is text content with an optional YAML
        front-matter, and that goes through the page pipeline.
    """
    def __init__(self, source, content_item):
        self.source = source
        self.content_item = content_item
        self._config = None
        self._segments = None
        self._flags = FLAG_NONE
        self._datetime = None

    @cached_property
    def app(self):
        return self.source.app

    @cached_property
    def route(self):
        return self.source.route

    @property
    def source_metadata(self):
        return self.content_item.metadata

    @property
    def content_spec(self):
        return self.content_item.spec

    @cached_property
    def content_mtime(self):
        return self.source.getItemMtime(self.content_item)

    @property
    def flags(self):
        return self._flags

    @property
    def config(self):
        self._load()
        return self._config

    @property
    def segments(self):
        self._load()
        return self._segments

    @property
    def datetime(self):
        if self._datetime is None:
            try:
                self._datetime = _compute_datetime(self.source_metadata,
                                                   self.config)
            except Exception as ex:
                logger.exception(ex)
                raise Exception(
                    "Error computing time for page: %s" %
                    self.content_spec) from ex

            if self._datetime is None:
                self._datetime = datetime.datetime.fromtimestamp(
                    self.content_mtime)

        return self._datetime

    @datetime.setter
    def datetime(self, value):
        self._datetime = value

    @property
    def was_modified(self):
        return (self._flags & FLAG_RAW_CACHE_VALID) == 0

    def getUri(self, sub_num=1):
        route_params = self.source_metadata['route_params']
        return self.route.getUri(route_params, sub_num=sub_num)

    def getSegment(self, name='content'):
        return self.segments[name]

    def _load(self):
        if self._config is not None:
            return

        config, content, was_cache_valid = load_page(
            self.source, self.content_item)

        extra_config = self.source_metadata.get('config')
        if extra_config is not None:
            # Merge the source metadata configuration settings with the
            # configuration settings from the page's contents. We only
            # prepend to lists, i.e. we don't overwrite values because we
            # want to keep what the user wrote in the file.
            config.merge(extra_config, mode=MERGE_PREPEND_LISTS)

        self._config = config
        self._segments = content
        if was_cache_valid:
            self._flags |= FLAG_RAW_CACHE_VALID


def _compute_datetime(source_metadata, config):
    # Get the date/time from the source.
    dt = source_metadata.get('datetime')
    if dt is not None:
        return dt

    # Get the date from the source. Potentially get the
    # time from the page config.
    page_date = source_metadata.get('date')
    if page_date is not None:
        dt = datetime.datetime(
            page_date.year, page_date.month, page_date.day)

        page_time = _parse_config_time(config.get('time'))
        if page_time is not None:
            dt += page_time

        return dt

    # Get the date from the page config, and maybe the
    # time too.
    page_date = _parse_config_date(config.get('date'))
    if page_date is not None:
        dt = datetime.datetime(
            page_date.year, page_date.month, page_date.day)

        page_time = _parse_config_time(config.get('time'))
        if page_time is not None:
            dt += page_time

        return dt

    # No idea what the date/time for this page is.
    return None


def _parse_config_date(page_date):
    if page_date is None:
        return None

    if isinstance(page_date, str):
        import dateutil.parser
        try:
            parsed_d = dateutil.parser.parse(page_date)
        except Exception as ex:
            logger.exception(ex)
            raise ConfigurationError("Invalid date: %s" % page_date) from ex
        return datetime.date(
            year=parsed_d.year,
            month=parsed_d.month,
            day=parsed_d.day)

    raise ConfigurationError("Invalid date: %s" % page_date)


def _parse_config_time(page_time):
    if page_time is None:
        return None

    if isinstance(page_time, datetime.timedelta):
        return page_time

    if isinstance(page_time, str):
        import dateutil.parser
        try:
            parsed_t = dateutil.parser.parse(page_time)
        except Exception as ex:
            logger.exception(ex)
            raise ConfigurationError("Invalid time: %s" % page_time) from ex
        return datetime.timedelta(
            hours=parsed_t.hour,
            minutes=parsed_t.minute,
            seconds=parsed_t.second)

    if isinstance(page_time, int):
        # Total seconds... convert to a time struct.
        return datetime.timedelta(seconds=page_time)

    raise ConfigurationError("Invalid time: %s" % page_time)


class PageLoadingError(Exception):
    def __init__(self, spec):
        super().__init__("Error loading page: %s" % spec)


class ContentSegment(object):
    debug_render_func = 'debug_render'

    def __init__(self, content, fmt=None, offset=-1, line=-1):
        self.content = content
        self.fmt = fmt
        self.offset = offset
        self.line = line

    def debug_render(self):
        return '[%s] %s' % (self.fmt or '<none>', self.content)


def json_load_segments(data):
    segments = {}
    for key, sd in data.items():
        seg = ContentSegment(sd['c'], sd['f'], sd['o'], sd['l'])
        segments[key] = seg
    return segments


def json_save_segments(segments):
    data = {}
    for key, seg in segments.items():
        seg_data = {
            'c': seg.content, 'f': seg.fmt, 'o': seg.offset, 'l': seg.line}
        data[key] = seg_data
    return data


def load_page(source, content_item):
    try:
        with source.app.env.stats.timerScope('PageLoad'):
            return _do_load_page(source, content_item)
    except Exception as e:
        logger.exception("Error loading page: %s" % content_item.spec)
        raise PageLoadingError(content_item.spec) from e


def _do_load_page(source, content_item):
    # Check the cache first.
    app = source.app
    cache = app.cache.getCache('pages')
    cache_token = "%s@%s" % (source.name, content_item.spec)
    cache_path = hashlib.md5(cache_token.encode('utf8')).hexdigest() + '.json'
    page_time = source.getItemMtime(content_item)
    if cache.isValid(cache_path, page_time):
        cache_data = json.loads(
            cache.read(cache_path),
            object_pairs_hook=collections.OrderedDict)
        config = PageConfiguration(
            values=cache_data['config'],
            validate=False)
        content = json_load_segments(cache_data['content'])
        return config, content, True

    # Nope, load the page from the source file.
    logger.debug("Loading page configuration from: %s" % content_item.spec)
    with source.openItem(content_item, 'r', encoding='utf-8') as fp:
        raw = fp.read()
    header, offset = parse_config_header(raw)

    config = PageConfiguration(header)
    content = parse_segments(raw, offset)
    config.set('segments', list(content.keys()))

    # Save to the cache.
    cache_data = {
        'config': config.getAll(),
        'content': json_save_segments(content)}
    cache.write(cache_path, json.dumps(cache_data))

    app.env.stats.stepCounter('PageLoads')

    return config, content, False


segment_pattern = re.compile(
    r"^\-\-\-[ \t]*(?P<name>\w+)(\:(?P<fmt>\w+))?[ \t]*\-\-\-[ \t]*$", re.M)


def _count_lines(txt, start=0, end=-1):
    cur = start
    line_count = 1
    while True:
        nex = txt.find('\n', cur)
        if nex < 0 or (end >= 0 and nex >= end):
            break

        cur = nex + 1
        line_count += 1

        if end >= 0 and cur >= end:
            break

    return line_count


def _string_needs_parsing(txt, offset):
    txtlen = len(txt)
    index = txt.find('-', offset)
    while index >= 0 and index < txtlen - 8:
        # Look for a potential `---segment---`
        if (index > 0 and
                txt[index - 1] == '\n' and
                txt[index + 1] == '-' and txt[index + 2] == '-'):
            return True
        index = txt.find('-', index + 1)
    return False


def parse_segments(raw, offset=0):
    # Get the number of lines in the header.
    header_lines = _count_lines(raw, 0, offset)
    current_line = header_lines

    # Figure out if we need any parsing.
    do_parse = _string_needs_parsing(raw, offset)
    if not do_parse:
        seg = ContentSegment(raw[offset:], None, offset, current_line)
        return {'content': seg}

    # Start parsing segments.
    matches = list(segment_pattern.finditer(raw, offset))
    num_matches = len(matches)
    if num_matches > 0:
        contents = {}

        first_offset = matches[0].start()
        if first_offset > 0:
            # There's some default content segment at the beginning.
            seg = ContentSegment(
                raw[offset:first_offset], None, offset, current_line)
            current_line += _count_lines(seg.content)
            contents['content'] = seg

        for i in range(1, num_matches):
            m1 = matches[i - 1]
            m2 = matches[i]

            cur_seg_start = m1.end() + 1
            cur_seg_end = m2.start()

            seg = ContentSegment(
                raw[cur_seg_start:cur_seg_end],
                m1.group('fmt'),
                cur_seg_start,
                current_line)
            current_line += _count_lines(seg.content)
            contents[m1.group('name')] = seg

        # Handle text past the last match.
        lastm = matches[-1]

        last_seg_start = lastm.end() + 1

        seg = ContentSegment(
            raw[last_seg_start:],
            lastm.group('fmt'),
            last_seg_start,
            current_line)
        contents[lastm.group('name')] = seg
        # No need to count lines for the last one.

        return contents
    else:
        # No segments, just content.
        seg = ContentSegment(raw[offset:], None, offset, current_line)
        return {'content': seg}
