import os.path
from foodtruck.config import FoodTruckConfig


default_config = os.path.join(
        os.path.dirname(__file__),
        '..',
        'foodtruck',
        'foodtruck.cfg.defaults')


def test_getcomplex_option():
    cstr = '''[foo]
    bar.name = My bar
    bar.path = /path/to/bar
    '''
    c = FoodTruckConfig(None, None)
    c.load_from_string(cstr)
    expected = {'name': "My bar", 'path': '/path/to/bar'}
    assert c.getcomplex('foo', 'bar') == expected

