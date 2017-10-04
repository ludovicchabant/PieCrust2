import os
import os.path
import sys
import copy
import logging
import threading
import subprocess
from flask import request
from piecrust.app import PieCrustFactory


logger = logging.getLogger(__name__)


class UnauthorizedSiteAccessError(Exception):
    pass


class InvalidSiteError(Exception):
    pass


class SiteInfo:
    def __init__(self, root_dir, *, debug=False):
        self.root_dir = root_dir
        self.debug = debug
        self._piecrust_factory = None
        self._piecrust_app = None
        self._scm = None

    @property
    def url_prefix(self):
        return request.script_root

    def make_url(self, rel_url):
        return self.url_prefix + rel_url

    @property
    def piecrust_factory(self):
        if self._piecrust_factory is None:
            self._piecrust_factory = PieCrustFactory(
                self.root_dir,
                cache_key='admin',
                debug=self.debug,
                config_values=[
                    ('site/root', self.make_url('/preview/')),
                    ('site/asset_url_format', self.make_url(
                        '/preview/_asset/%path%'))]
            )
        return self._piecrust_factory

    @property
    def piecrust_app(self):
        if self._piecrust_app is None:
            logger.debug("Creating PieCrust admin app: %s" % self.root_dir)
            self._piecrust_app = self.piecrust_factory.create()
        return self._piecrust_app

    @property
    def scm(self):
        if self._scm is None:
            cfg = copy.deepcopy(self.piecrust_app.config.get('scm', {}))

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
            sys.executable, sys.argv[0],
            '--pid-file', self.publish_pid_file,
            'publish',
            '--log-publisher', self.publish_log_file,
            target]
        logger.debug("Running publishing command: %s" % args)
        proc = subprocess.Popen(args, cwd=self.root_dir)

        def _comm():
            proc.communicate()

        t = threading.Thread(target=_comm, daemon=True)
        t.start()

