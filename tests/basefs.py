import os.path
import yaml
from piecrust.app import PieCrust
from piecrust.sources.base import ContentItem


class TestFileSystemBase(object):
    _use_chef_debug = False
    _pytest_log_handler = None
    _leave_mockfs = False

    def __init__(self):
        pass

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

    def getApp(self, *, cache=True, theme_site=False):
        root_dir = self.path('/kitchen')
        return PieCrust(root_dir, cache=cache, debug=True,
                        theme_site=theme_site)

    def withDir(self, path):
        path = self.path(path)
        self._createDir(path)
        return self

    def withFile(self, path, contents):
        path = self.path(path)
        self._createFile(path, contents)
        return self

    def withAsset(self, path, contents):
        return self.withFile('kitchen/' + path, contents)

    def withAssetDir(self, path):
        return self.withDir('kitchen/' + path)

    def withConfig(self, config=None):
        if config is None:
            config = {}
        return self.withFile(
            'kitchen/config.yml',
            yaml.dump(config, default_flow_style=False))

    def withThemeConfig(self, config):
        return self.withFile(
            'kitchen/theme_config.yml',
            yaml.dump(config, default_flow_style=False))

    def withPage(self, url, config=None, contents=None):
        config = config or {}
        contents = contents or "A test page."
        text = "---\n"
        text += yaml.dump(config, default_flow_style=False)
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

    def runChef(self, *args):
        root_dir = self.path('/kitchen')
        chef_args = ['--root', root_dir]
        if self._use_chef_debug:
            chef_args += ['--debug']
        chef_args += list(args)

        import logging
        from piecrust.main import (
            _make_chef_state, _recover_pre_chef_state,
            _pre_parse_chef_args, _run_chef)

        # If py.test added a log handler, remove it because Chef will
        # add its own logger.
        if self._pytest_log_handler:
            logging.getLogger().removeHandler(
                self._pytest_log_handler)

        state = _make_chef_state()
        pre_args = _pre_parse_chef_args(chef_args, state=state)
        exit_code = _run_chef(pre_args, chef_args)
        _recover_pre_chef_state(state)

        if self._pytest_log_handler:
            logging.getLogger().addHandler(
                self._pytest_log_handler)

        assert exit_code == 0

    def getSimplePage(self, rel_path):
        app = self.getApp()
        source = app.getSource('pages')
        content_item = ContentItem(
            os.path.join(source.fs_endpoint_path, rel_path),
            {'route_params': {
                'slug': os.path.splitext(rel_path)[0]}})
        return app.getPage(source, content_item)

