import os
import os.path
import sys
import copy
import logging
import subprocess
from flask import flash
from piecrust import CACHE_DIR
from piecrust.app import PieCrustFactory


logger = logging.getLogger(__name__)


class UnauthorizedSiteAccessError(Exception):
    pass


class InvalidSiteError(Exception):
    pass


class SiteInfo:
    def __init__(self, root_dir, *, url_prefix='', debug=False):
        self.root_dir = root_dir
        self.url_prefix = url_prefix
        self.debug = debug
        self._piecrust_factory = None
        self._piecrust_app = None
        self._scm = None

    def make_url(self, rel_url):
        prefix = self.url_prefix
        if not prefix:
            return rel_url
        return prefix + rel_url

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

    def rebakeAssets(self):
        out_dir = os.path.join(
            self.root_dir,
            CACHE_DIR,
            self.piecrust_factory.cache_key,
            'server')
        args = [
            '--no-color',
            'bake',
            '-o', out_dir,
            '--assets-only']
        proc = self._runChef(args)
        try:
            proc.wait(timeout=2)
            if proc.returncode == 0:
                flash("Assets baked successfully!")
            else:
                flash("Asset baking process returned '%s'... check the log." %
                      proc.returncode)
        except subprocess.TimeoutExpired:
            flash("Asset baking process is still running... "
                  "check the log later.")

    def getPublishTargetLogFile(self, target):
        target = target.replace(' ', '_').lower()
        return os.path.join(self.piecrust_app.cache_dir,
                            'publish.%s.log' % target)

    def publish(self, target):
        args = [
            '--no-color',
            '--pid-file', self.publish_pid_file,
            '--log', self.publish_log_file,
            'publish',
            '--log-publisher', self.getPublishTargetLogFile(target),
            '--log-debug-info',
            target]
        proc = self._runChef(args)
        try:
            proc.wait(timeout=2)
            if proc.returncode == 0:
                flash("Publish process ran successfully!")
            else:
                flash("Publish process returned '%s'... check the log." %
                      proc.returncode)
        except subprocess.TimeoutExpired:
            flash("Publish process is still running... check the log later.")

    def runTask(self, task_id):
        args = [
            '--no-color',
            'tasks', 'run',
            '-t', task_id]
        self._runChef(args)

    def _runChef(self, args):
        chef_path = os.path.realpath(os.path.join(
            os.path.dirname(__file__),
            '../../chef.py'))
        args = [sys.executable, chef_path] + args

        env = {}
        for k, v in os.environ.items():
            env[k] = v
        env['PYTHONHOME'] = sys.prefix

        logger.info("Running chef command: %s" % args)
        proc = subprocess.Popen(args, cwd=self.root_dir, env=env)
        logger.info("Chef process ID: %s" % proc.pid)
        return proc
