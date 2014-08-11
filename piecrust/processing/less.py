import os
import os.path
import json
import hashlib
import logging
import subprocess
from piecrust.processing.base import SimpleFileProcessor
from piecrust.processing.tree import FORCE_BUILD


logger = logging.getLogger(__name__)


class LessProcessor(SimpleFileProcessor):
    PROCESSOR_NAME = 'less'

    def __init__(self):
        super(LessProcessor, self).__init__({'less': 'css'})
        self._conf = None
        self._map_dir = None

    def onPipelineStart(self, pipeline):
        self._map_dir = os.path.join(pipeline.tmp_dir, 'less')
        if not os.path.isdir(self._map_dir):
            os.makedirs(self._map_dir)

    def getDependencies(self, path):
        map_path = self._getMapPath(path)
        try:
            with open(map_path, 'r') as f:
                dep_map = json.load(f)
            source = dep_map.get('sources')
            # The last one is always the file itself, so skip that. Also,
            # make all paths absolute.
            path_dir = os.path.dirname(path)
            def _makeAbs(p):
                return os.path.join(path_dir, p)
            return map(_makeAbs, source[:-1])
        except IOError:
            # Map file not found... rebuild.
            logger.debug("No map file found for LESS file '%s' at '%s'. "
                         "Rebuilding" % (path, map_path))
            return FORCE_BUILD

    def _doProcess(self, in_path, out_path):
        self._ensureInitialized()

        map_path = self._getMapPath(in_path)
        map_path = os.path.relpath(map_path)
        args = [self._conf['bin'], '--source-map=%s' % map_path]
        args += self._conf['options']
        args.append(in_path)
        args.append(out_path)
        logger.debug("Processing LESS file: %s" % args)
        retcode = subprocess.call(args)
        if retcode != 0:
            raise Exception("Error occured in LESS compiler. Please check "
                            "log messages above for more information.")
        return True

    def _ensureInitialized(self):
        if self._conf is not None:
            return

        self._conf = self.app.config.get('less') or {}
        self._conf.setdefault('bin', 'lessc')
        self._conf.setdefault('options',
                ['--compress'])
        if not isinstance(self._conf['options'], list):
            raise Exception("The `less/options` configuration setting "
                            "must be an array of arguments.")

    def _getMapPath(self, path):
        map_name = "%s.map" % hashlib.md5(path).hexdigest()
        map_path = os.path.join(self._map_dir, map_name)
        return map_path

