import os
import os.path
import copy
import shlex
import logging
import threading
import subprocess
from piecrust.app import PieCrust


logger = logging.getLogger(__name__)


class UnauthorizedSiteAccessError(Exception):
    pass


class Site(object):
    def __init__(self, name, root_dir, config):
        self.name = name
        self.root_dir = root_dir
        self.config = config
        self._piecrust_app = None
        self._scm = None
        self._bake_thread = None
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
            cfg = None
            scm_cfg = self.config.get('sites/%s/scm' % self.name)
            global_scm_cfg = self.config.get('scm')
            if scm_cfg:
                if global_scm_cfg:
                    cfg = copy.deepcopy(global_scm_cfg)
                    merge_dicts(cfg, scm_cfg)
                else:
                    cfg = copy.deepcopy(scm_cfg)
            elif global_scm_cfg:
                cfg = copy.deepcopy(global_scm_cfg)

            if not cfg or not 'type' in cfg:
                raise Exception("No SCM available for site: %s" % self.name)

            if cfg['type'] == 'hg':
                from .scm.mercurial import MercurialSourceControl
                self._scm = MercurialSourceControl(self.root_dir, cfg)
            else:
                raise NotImplementedError()

        return self._scm

    @property
    def is_bake_running(self):
        return self._bake_thread is not None and self._bake_thread.is_alive()

    @property
    def bake_thread(self):
        return self._bake_thread

    def bake(self):
        bake_cmd = self.config.get('triggers/bake')
        bake_args = shlex.split(bake_cmd)

        logger.debug("Running bake: %s" % bake_args)
        proc = subprocess.Popen(bake_args, cwd=self.root_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)

        pid_file_path = os.path.join(self.root_dir, 'foodtruck_bake.pid')
        with open(pid_file_path, 'w') as fp:
            fp.write(str(proc.pid))

        logger.debug("Running bake monitor for PID %d" % proc.pid)
        self._bake_thread = _BakeThread(self.name, self.root_dir, proc,
                                        self._onBakeEnd)
        self._bake_thread.start()

    def _onBakeEnd(self):
        os.unlink(os.path.join(self.root_dir, 'foodtruck_bake.pid'))
        self._bake_thread = None


class _BakeThread(threading.Thread):
    def __init__(self, sitename, siteroot, proc, callback):
        super(_BakeThread, self).__init__(
                name='%s_bake' % sitename, daemon=True)
        self.sitename = sitename
        self.siteroot = siteroot
        self.proc = proc
        self.callback = callback

        log_file_path = os.path.join(self.siteroot, 'foodtruck_bake.log')
        self.log_fp = open(log_file_path, 'w', encoding='utf8')

    def run(self):
        for line in self.proc.stdout:
            self.log_fp.write(line.decode('utf8'))
        for line in self.proc.stderr:
            self.log_fp.write(line.decode('utf8'))
        self.proc.communicate()
        if self.proc.returncode != 0:
            self.log_fp.write("Error, bake process returned code %d" %
                              self.proc.returncode)
        self.log_fp.close()

        logger.debug("Bake ended for %s." % self.sitename)
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
            raise Exception("No such site: %s" % name)
        root_dir = scfg.get('path')
        if root_dir is None:
            raise Exception("Site '%s' has no path defined." % name)
        if not os.path.isdir(root_dir):
            raise Exception("Site '%s' has an invalid path." % name)
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

