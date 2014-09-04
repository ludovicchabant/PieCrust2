import sys
import logging


def pytest_runtest_setup(item):
    pass


def pytest_addoption(parser):
    parser.addoption('--log-debug', action='store_true',
            help="Sets the PieCrust logger to output debug info to stdout.")


def pytest_configure(config):
    if config.getoption('--log-debug'):
        hdl = logging.StreamHandler(stream=sys.stdout)
        logging.getLogger('piecrust').addHandler(hdl)
        logging.getLogger('piecrust').setLevel(logging.DEBUG)

