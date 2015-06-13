import os.path
import yaml
from piecrust.app import PieCrust


class TestFileSystemBase(object):
    def __init__(self):
        pass

    def _initDefaultSpec(self):
        self.withDir('counter')
        self.withFile(
                'kitchen/config.yml',
                "site:\n  title: Mock Website\n")

    def path(self, p):
        raise NotImplementedError()

    def getStructure(self, path=None):
        raise NotImplementedError()

    def getFileEntry(self, path):
        raise NotImplementedError()

    def _createDir(self, path):
        raise NotImplementedError()

    def _createFile(self, path, contents):
        raise NotImplementedError()

    def getApp(self, cache=True):
        root_dir = self.path('/kitchen')
        return PieCrust(root_dir, cache=cache, debug=True)

    def withDir(self, path):
        path = path.replace('\\', '/')
        path = path.lstrip('/')
        path = '/%s/%s' % (self._root, path)
        self._createDir(path)
        return self

    def withFile(self, path, contents):
        path = path.replace('\\', '/')
        path = path.lstrip('/')
        path = '/%s/%s' % (self._root, path)
        self._createFile(path, contents)
        return self

    def withAsset(self, path, contents):
        return self.withFile('kitchen/' + path, contents)

    def withAssetDir(self, path):
        return self.withDir('kitchen/' + path)

    def withConfig(self, config):
        return self.withFile(
                'kitchen/config.yml',
                yaml.dump(config))

    def withThemeConfig(self, config):
        return self.withFile(
                'kitchen/theme/theme_config.yml',
                yaml.dump(config))

    def withPage(self, url, config=None, contents=None):
        config = config or {}
        contents = contents or "A test page."
        text = "---\n"
        text += yaml.dump(config)
        text += "---\n"
        text += contents

        name, ext = os.path.splitext(url)
        if not ext:
            url += '.md'
        url = url.lstrip('/')
        return self.withAsset(url, text)

    def withPageAsset(self, page_url, name, contents=None):
        contents = contents or "A test asset."
        url_base, ext = os.path.splitext(page_url)
        dirname = url_base + '-assets'
        return self.withAsset(
                '%s/%s' % (dirname, name), contents)

    def withPages(self, num, url_factory, config_factory=None,
                  contents_factory=None):
        for i in range(num):
            if isinstance(url_factory, str):
                url = url_factory.format(idx=i, idx1=(i + 1))
            else:
                url = url_factory(i)

            config = None
            if config_factory:
                config = config_factory(i)

            contents = None
            if contents_factory:
                contents = contents_factory(i)

            self.withPage(url, config, contents)
        return self

