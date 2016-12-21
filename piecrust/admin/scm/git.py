import os
import logging
import tempfile
import subprocess
from .base import SourceControl, RepoStatus, _s


logger = logging.getLogger(__name__)


class GitSourceControl(SourceControl):
    def __init__(self, root_dir, cfg):
        super(GitSourceControl, self).__init__(root_dir, cfg)
        self.git = cfg.get('exe', 'git')

    def getStatus(self):
        res = RepoStatus()
        st_out = self._run('status', '-s')
        for line in st_out.split('\n'):
            if not line:
                continue
            if line.startswith('?? '):
                path = line[3:].strip()
                if path[-1] == '/':
                    import glob
                    res.new_files += [
                        f for f in glob.glob(path + '**', recursive=True)
                        if f[-1] != '/']
                else:
                    res.new_files.append(path)
            elif line.startswith(' M '):
                res.edited_files.append(line[3:])
        return res

    def _doCommit(self, paths, message, author):
        self._run('add', *paths)

        # Create a temp file with the commit message.
        f, temp = tempfile.mkstemp()
        with os.fdopen(f, 'w') as fd:
            fd.write(message)

        # Commit and clean up the temp file.
        try:
            commit_args = list(paths) + ['-F', temp]
            if author:
                commit_args += ['--author="%s"' % author]
            self._run('commit', *commit_args)
        finally:
            os.remove(temp)

    def _run(self, cmd, *args, **kwargs):
        exe = [self.git]
        exe.append(cmd)
        exe += args

        logger.debug("Running Git: " + str(exe))
        proc = subprocess.Popen(
            exe, stdout=subprocess.PIPE, cwd=self.root_dir)
        out, _ = proc.communicate()

        encoded_out = _s(out)
        return encoded_out

