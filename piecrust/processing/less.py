import os
import os.path
import sys
import json
import hashlib
import logging
import platform
import subprocess
from piecrust.processing.base import (
    SimpleFileProcessor, ExternalProcessException, FORCE_BUILD)


logger = logging.getLogger(__name__)


class LessProcessor(SimpleFileProcessor):
    PROCESSOR_NAME = 'less'

    def __init__(self):
        super(LessProcessor, self).__init__({'less': 'css'})
        self._conf = None
        self._map_dir = None

    def onPipelineStart(self, ctx):
        self._map_dir = os.path.join(ctx.tmp_dir, 'less')
        if (ctx.is_main_process and
                not os.path.isdir(self._map_dir)):
            os.makedirs(self._map_dir)

    def getDependencies(self, path):
        map_path = self._getMapPath(path)
        try:
            with open(map_path, 'r') as f:
                dep_map = json.load(f)
        except OSError:
            # Map file not found... rebuild.
            logger.debug("No map file found for LESS file '%s' at '%s'. "
                         "Rebuilding" % (path, map_path))
            return FORCE_BUILD

        # Check the version, since the `sources` list has changed
        # meanings over time.
        if dep_map.get('version') != 3:
            logger.warning("Unknown LESS map version. Force rebuilding.")
            return FORCE_BUILD

        # Get the sources, but make all paths absolute.
        sources = dep_map.get('sources')
        path_dir = os.path.dirname(path)

        def _makeAbs(p):
            return os.path.join(path_dir, p)
        deps = list(map(_makeAbs, sources))
        return deps

    def _doProcess(self, in_path, out_path):
        self._ensureInitialized()

        map_path = self._getMapPath(in_path)
        map_url = '/' + os.path.relpath(
            map_path, self.app.root_dir).replace('\\', '/')

        # On Windows, it looks like LESSC is confused with paths when the
        # map file is not to be created in the same directory as the input
        # file (it ends up writing invalid dependencies in the map file, with
        # a mix of relative and absolute paths stuck together).
        # So create it there and move it afterwards... :(
        temp_map_path = os.path.join(
            os.path.dirname(in_path),
            os.path.basename(map_path))

        args = [self._conf['bin'],
                '--source-map=%s' % temp_map_path,
                '--source-map-url=%s' % map_url]
        args += self._conf['options']
        args.append(in_path)
        args.append(out_path)
        logger.debug("Processing LESS file: %s" % args)

        try:
            proc = subprocess.Popen(args, stderr=subprocess.PIPE)
            stdout_data, stderr_data = proc.communicate()
        except FileNotFoundError as ex:
            logger.error("Tried running LESS processor with command: %s" %
                         args)
            raise Exception("Error running LESS processor. "
                            "Did you install it?") from ex
        if proc.returncode != 0:
            raise ExternalProcessException(
                stderr_data.decode(sys.stderr.encoding))

        logger.debug("Moving map file: %s -> %s" % (temp_map_path, map_path))
        if os.path.exists(map_path):
            os.remove(map_path)
        os.rename(temp_map_path, map_path)

        return True

    def _ensureInitialized(self):
        if self._conf is not None:
            return

        bin_name = 'lessc'
        if platform.system() == 'Windows':
            bin_name += '.cmd'

        self._conf = self.app.config.get('less') or {}
        self._conf.setdefault('bin', bin_name)
        self._conf.setdefault('options', ['--compress'])
        if not isinstance(self._conf['options'], list):
            raise Exception("The `less/options` configuration setting "
                            "must be an array of arguments.")

    def _getMapPath(self, path):
        map_name = "%s_%s.map" % (
            os.path.basename(path),
            hashlib.md5(path.encode('utf8')).hexdigest())
        map_path = os.path.join(self._map_dir, map_name)
        return map_path

