import os
import logging
import tempfile
import subprocess
from .base import SourceControl, RepoStatus, _s


logger = logging.getLogger(__name__)


class MercurialSourceControl(SourceControl):
    def __init__(self, root_dir, cfg):
        super(MercurialSourceControl, self).__init__(root_dir, cfg)
        self.hg = cfg.get('exe', 'hg')

    def getStatus(self):
        res = RepoStatus()
        st_out = self._run('status')
        for line in st_out.split('\n'):
            if len(line) == 0:
                continue
            if line[0] == '?' or line[0] == 'A':
                res.new_files.append(line[2:])
            elif line[0] == 'M':
                res.edited_files.append(line[2:])
        return res

    def _doCommit(self, paths, message, author):
        # Check if any of those paths needs to be added.
        st_out = self._run('status', *paths)
        add_paths = []
        for line in st_out.splitlines():
            if line[0] == '?':
                add_paths.append(line[2:])
        if len(add_paths) > 0:
            self._run('add', *paths)

        # Create a temp file with the commit message.
        f, temp = tempfile.mkstemp()
        with os.fdopen(f, 'w') as fd:
            fd.write(message)

        # Commit and clean up the temp file.
        try:
            commit_args = list(paths) + ['-l', temp]
            if author:
                commit_args += ['-u', author]
            self._run('commit', *commit_args)
        finally:
            os.remove(temp)

    def _run(self, cmd, *args, **kwargs):
        exe = [self.hg, '-R', self.root_dir]
        exe.append(cmd)
        exe += args

        env = dict(os.environ)
        env['HGPLAIN'] = 'True'

        logger.debug("Running Mercurial: " + str(exe))
        proc = subprocess.Popen(exe, stdout=subprocess.PIPE, env=env)
        out, _ = proc.communicate()

        encoded_out = _s(out)
        return encoded_out

