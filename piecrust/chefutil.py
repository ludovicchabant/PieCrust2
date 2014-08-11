import time
from colorama import Fore


def format_timed(start_time, message, colored=True):
    end_time = time.clock()
    time_str = '%8.1f ms' % ((end_time - start_time) * 1000.0)
    if colored:
        return '[%s%s%s] %s' % (Fore.GREEN, time_str, Fore.RESET, message)
    return '[%s] %s' % (time_str, message)

