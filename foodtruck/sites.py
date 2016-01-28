import os
import os.path
import copy
import shlex
import logging
import threading
import subprocess
from piecrust.app import PieCrust
from piecrust.configuration import merge_dicts, Configuration


logger = logging.getLogger(__name__)


class UnauthorizedSiteAccessError(Exception):
    pass


class InvalidSiteError(Exception):
    pass


class Site(object):
    def __init__(self, name, root_dir, config):
        self.name = name
        self.root_dir = root_dir
        self.config = Configuration(values=config.get('sites/%s' % name, {}))
        self._global_config = config
        self._piecrust_app = None
        self._scm = None
        self._publish_thread = None
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
            merge_dicts(cfg, self.config.get('scm', {}))

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
    def is_publish_running(self):
        return (self._publish_thread is not None and
                self._publish_thread.is_alive())

    @property
    def publish_thread(self):
        return self._publish_thread

    def publish(self, target):
        target_cfg = self.config.get('publish/%s' % target)
        if not target_cfg:
            raise Exception("No such publish target: %s" % target)

        target_cmd = target_cfg.get('cmd')
        if not target_cmd:
            raise Exception("No command specified for publish target: %s" %
                            target)
        publish_args = shlex.split(target_cmd)

        logger.debug(
                "Executing publish target '%s': %s" % (target, publish_args))
        proc = subprocess.Popen(publish_args, cwd=self.root_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        pid_file_path = os.path.join(self.root_dir, '.ft_pub.pid')
        with open(pid_file_path, 'w') as fp:
            fp.write(str(proc.pid))

        logger.debug("Running publishing monitor for PID %d" % proc.pid)
        self._publish_thread = _PublishThread(
                self.name, self.root_dir, proc, self._onPublishEnd)
        self._publish_thread.start()

    def _onPublishEnd(self):
        os.unlink(os.path.join(self.root_dir, '.ft_pub.pid'))
        self._publish_thread = None


class _PublishThread(threading.Thread):
    def __init__(self, sitename, siteroot, proc, callback):
        super(_PublishThread, self).__init__(
                name='%s_publish' % sitename, daemon=True)
        self.sitename = sitename
        self.siteroot = siteroot
        self.proc = proc
        self.callback = callback

        log_file_path = os.path.join(self.siteroot, '.ft_pub.log')
        self.log_fp = open(log_file_path, 'w', encoding='utf8')

    def run(self):
        for line in self.proc.stdout:
            self.log_fp.write(line.decode('utf8'))
        for line in self.proc.stderr:
            self.log_fp.write(line.decode('utf8'))
        self.proc.communicate()
        if self.proc.returncode != 0:
            self.log_fp.write("Error, publish process returned code %d" %
                              self.proc.returncode)
        self.log_fp.close()

        logger.debug("Publish ended for %s." % self.sitename)
        self.callback()


class FoodTruckSites():
    def __init__(self, config, current_site):
        self._sites = {}
        self._site_dirs = {}
        self.config = config
        self.current_site = current_site
        if current_site is None:
            raise Exception("No current site was given.")

    def get_root_dir(self, name=None):
        name = name or self.current_site
        s = self._site_dirs.get(name)
        if s:
            return s

        scfg = self.config.get('sites/%s' % name)
        if scfg is None:
            raise InvalidSiteError("No such site: %s" % name)
        root_dir = scfg.get('path')
        if root_dir is None:
            raise InvalidSiteError("Site '%s' has no path defined." % name)
        if not os.path.isdir(root_dir):
            raise InvalidSiteError("Site '%s' has an invalid path." % name)
        self._site_dirs[name] = root_dir
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

