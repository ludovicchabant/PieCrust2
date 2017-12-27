from .mockutil import mock_fs, mock_fs_scope


def test_no_plugins():
    fs = (mock_fs()
          .withConfig())
    with mock_fs_scope(fs):
        app = fs.getApp()
        assert len(app.plugin_loader.plugins) == 1
        assert app.plugin_loader.plugins[0].name == '__builtin__'


testplug_code = """from piecrust.plugins.base import PieCrustPlugin

class TestPlugPlugin(PieCrustPlugin):
    name = 'just a test plugin'

__piecrust_plugin__ = TestPlugPlugin
"""

def test_loose_file():
    fs = (mock_fs()
          .withConfig({'site': {'plugins': 'testplug'}})
          .withFile('kitchen/plugins/testplug.py', testplug_code))
    with mock_fs_scope(fs):
        app = fs.getApp()
        assert sorted([p.name for p in app.plugin_loader.plugins]) == \
          sorted(['__builtin__', 'just a test plugin'])
