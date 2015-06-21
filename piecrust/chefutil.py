import time
import logging
import contextlib
from colorama import Fore


@contextlib.contextmanager
def format_timed_scope(logger, message, *, level=logging.INFO, colored=True,
                       timer_env=None, timer_category=None):
    start_time = time.perf_counter()
    yield
    logger.log(level, format_timed(start_time, message, colored=colored))
    if timer_env is not None and timer_category is not None:
        timer_env.stepTimer(timer_category, time.perf_counter() - start_time)


def format_timed(start_time, message, indent_level=0, colored=True):
    end_time = time.perf_counter()
    indent = indent_level * '  '
    time_str = '%8.1f ms' % ((end_time - start_time) * 1000.0)
    if colored:
        return '[%s%s%s] %s' % (Fore.GREEN, time_str, Fore.RESET, message)
    return '%s[%s] %s' % (indent, time_str, message)


def log_friendly_exception(logger, ex):
    indent = ''
    while ex:
        ex_msg = str(ex)
        if not ex_msg:
            ex_msg = '%s exception was thrown' % type(ex).__name__
        logger.error('%s%s' % (indent, ex_msg))
        indent += '  '
        ex = ex.__cause__


def print_help_item(s, title, description, margin=4, align=25):
    s.write(margin * ' ')
    s.write(title)
    spacer = (align - margin - len(title) - 1)
    if spacer <= 0:
        s.write("\n")
        s.write(' ' * align)
    else:
        s.write(' ' * spacer)
    s.write(description)
    s.write("\n")

