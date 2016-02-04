import os
import os.path
import copy
import logging
import threading
import subprocess
from piecrust.app import PieCrust
from piecrust.configuration import merge_dicts


logger = logging.getLogger(__name__)


class UnauthorizedSiteAccessError(Exception):
    pass


class InvalidSiteError(Exception):
    pass


class Site(object):
    def __init__(self, name, root_dir, config):
        self.name = name
        self.root_dir = root_dir
        self._global_config = config
        self._piecrust_app = None
        self._scm = None
        logger.debug("Creating site object for %s" % self.name)

    @property
    def piecrust_app(self):
        if self._piecrust_app is None:
            s = PieCrust(self.root_dir)
            s.config.set('site/root', '/site/%s/' % self.name)
            self._piecrust_app = s
        return self._piecrust_app

    @property
    def scm(self):
        if self._scm is None:
            cfg = copy.deepcopy(self._global_config.get('scm', {}))
            merge_dicts(cfg, self.piecrust_app.config.get('scm', {}))

            if os.path.isdir(os.path.join(self.root_dir, '.hg')):
                from .scm.mercurial import MercurialSourceControl
                self._scm = MercurialSourceControl(self.root_dir, cfg)
            elif os.path.isdir(os.path.join(self.root_dir, '.git')):
                from .scm.git import GitSourceControl
                self._scm = GitSourceControl(self.root_dir, cfg)
            else:
                self._scm = False

        return self._scm

    @property
    def publish_pid_file(self):
        return os.path.join(self.piecrust_app.cache_dir, 'publish.pid')

    @property
    def publish_log_file(self):
        return os.path.join(self.piecrust_app.cache_dir, 'publish.log')

    def publish(self, target):
        args = [
                'chef',
                '--pid-file', self.publish_pid_file,
                'publish', target,
                '--log-publisher', self.publish_log_file]
        proc = subprocess.Popen(args, cwd=self.root_dir)

        def _comm():
            proc.communicate()

        t = threading.Thread(target=_comm, daemon=True)
        t.start()


class FoodTruckSites():
    def __init__(self, config, current_site):
        self._sites = {}
        self.config = config
        self.current_site = current_site
        if current_site is None:
            raise Exception("No current site was given.")

    def get_root_dir(self, name=None):
        name = name or self.current_site
        root_dir = self.config.get('sites/%s' % name)
        if root_dir is None:
            raise InvalidSiteError("No such site: %s" % name)
        if not os.path.isdir(root_dir):
            raise InvalidSiteError("Site '%s' has an invalid path." % name)
        return root_dir

    def get(self, name=None):
        name = name or self.current_site
        s = self._sites.get(name)
        if s:
            return s

        root_dir = self.get_root_dir(name)
        s = Site(name, root_dir, self.config)
        self._sites[name] = s
        return s

    def getall(self):
        for name in self.config.get('sites'):
            yield self.get(name)

