import re
import time
import email.utils
import hashlib
import strict_rfc3339
from jinja2 import Environment
from .extensions import get_highlight_css
from piecrust.data.paginator import Paginator
from piecrust.rendering import format_text
from piecrust.uriutil import multi_replace


class PieCrustEnvironment(Environment):
    def __init__(self, app, *args, **kwargs):
        self.app = app

        # Before we create the base Environement, let's figure out the options
        # we want to pass to it.
        twig_compatibility_mode = app.config.get('jinja/twig_compatibility')

        # Disable auto-reload when we're baking.
        if app.config.get('baker/is_baking'):
            kwargs.setdefault('auto_reload', False)

        # Let the user override most Jinja options via the site config.
        for name in ['block_start_string', 'block_end_string',
                     'variable_start_string', 'variable_end_string',
                     'comment_start_string', 'comment_end_string',
                     'line_statement_prefix', 'line_comment_prefix',
                     'trim_blocks', 'lstrip_blocks',
                     'newline_sequence', 'keep_trailing_newline']:
            val = app.config.get('jinja/' + name)
            if val is not None:
                kwargs.setdefault(name, val)

        # Twig trims blocks.
        if twig_compatibility_mode is True:
            kwargs['trim_blocks'] = True

        # All good! Create the Environment.
        super(PieCrustEnvironment, self).__init__(*args, **kwargs)

        # Now add globals and filters.
        self.globals.update({
            'now': get_now_date(),
            'fail': raise_exception,
            'highlight_css': get_highlight_css})

        self.filters.update({
            'keys': get_dict_keys,
            'values': get_dict_values,
            'paginate': self._paginate,
            'formatwith': self._formatWith,
            'markdown': lambda v: self._formatWith(v, 'markdown'),
            'textile': lambda v: self._formatWith(v, 'textile'),
            'nocache': add_no_cache_parameter,
            'wordcount': get_word_count,
            'stripoutertag': strip_outer_tag,
            'stripslash': strip_slash,
            'titlecase': title_case,
            'md5': make_md5,
            'atomdate': get_xml_date,
            'xmldate': get_xml_date,
            'emaildate': get_email_date,
            'date': get_date})

        # Backwards compatibility with Twig.
        if twig_compatibility_mode is True:
            self.filters['raw'] = self.filters['safe']
            self.globals['pcfail'] = raise_exception

    def _paginate(self, value, items_per_page=5):
        cpi = self.app.env.exec_info_stack.current_page_info
        if cpi is None or cpi.page is None or cpi.render_ctx is None:
            raise Exception("Can't paginate when no page has been pushed "
                            "on the execution stack.")
        return Paginator(cpi.page, value,
                         page_num=cpi.render_ctx.page_num,
                         items_per_page=items_per_page)

    def _formatWith(self, value, format_name):
        return format_text(self.app, format_name, value)


def raise_exception(msg):
    raise Exception(msg)


def get_dict_keys(value):
    if isinstance(value, list):
        return [i[0] for i in value]
    return value.keys()


def get_dict_values(value):
    if isinstance(value, list):
        return [i[1] for i in value]
    return value.values()


def add_no_cache_parameter(value, param_name='t', param_value=None):
    if not param_value:
        param_value = time.time()
    if '?' in value:
        value += '&'
    else:
        value += '?'
    value += '%s=%s' % (param_name, param_value)
    return value


def get_word_count(value):
    return len(value.split())


def strip_outer_tag(value, tag=None):
    tag_pattern = '[a-z]+[a-z0-9]*'
    if tag is not None:
        tag_pattern = re.escape(tag)
    pat = r'^\<' + tag_pattern + r'\>(.*)\</' + tag_pattern + '>$'
    m = re.match(pat, value)
    if m:
        return m.group(1)
    return value


def strip_slash(value):
    return value.rstrip('/')


def title_case(value):
    return value.title()


def make_md5(value):
    return hashlib.md5(value.lower().encode('utf8')).hexdigest()


def get_xml_date(value):
    """ Formats timestamps like 1985-04-12T23:20:50.52Z
    """
    if value == 'now':
        value = time.time()
    return strict_rfc3339.timestamp_to_rfc3339_localoffset(int(value))


def get_email_date(value, localtime=False):
    """ Formats timestamps like Fri, 09 Nov 2001 01:08:47 -0000
    """
    if value == 'now':
        value = time.time()
    return email.utils.formatdate(value, localtime=localtime)


def get_now_date():
    return time.time()


def get_date(value, fmt):
    if value == 'now':
        value = time.time()
    if '%' not in fmt:
        suggest = php_format_to_strftime_format(fmt)
        if suggest != fmt:
            suggest_message = ("You probably want a format that looks "
                               "like: '%s'." % suggest)
        else:
            suggest_message = ("We can't suggest a proper date format "
                               "for you right now, though.")
        raise Exception("Got incorrect date format: '%s\n"
                        "PieCrust 1 date formats won't work in PieCrust 2. "
                        "%s\n"
                        "Please check the `strftime` formatting page here: "
                        "https://docs.python.org/3/library/datetime.html"
                        "#strftime-and-strptime-behavior" %
                        (fmt, suggest_message))
    return time.strftime(fmt, time.localtime(value))


def php_format_to_strftime_format(fmt):
    replacements = {
        'd': '%d',
        'D': '%a',
        'j': '%d',
        'l': '%A',
        'w': '%w',
        'z': '%j',
        'W': '%W',
        'F': '%B',
        'm': '%m',
        'M': '%b',
        'n': '%m',
        'y': '%Y',
        'Y': '%y',
        'g': '%I',
        'G': '%H',
        'h': '%I',
        'H': '%H',
        'i': '%M',
        's': '%S',
        'e': '%Z',
        'O': '%z',
        'c': '%Y-%m-%dT%H:%M:%SZ'}
    return multi_replace(fmt, replacements)
