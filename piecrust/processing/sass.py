import os
import os.path
import json
import hashlib
import logging
import platform
import subprocess
from piecrust.processing.base import SimpleFileProcessor, FORCE_BUILD


logger = logging.getLogger(__name__)


class SassProcessor(SimpleFileProcessor):
    PROCESSOR_NAME = 'sass'

    def __init__(self):
        super(SassProcessor, self).__init__(
            extensions={'scss': 'css', 'sass': 'css'})
        self._conf = None
        self._map_dir = None

    def initialize(self, app):
        super(SassProcessor, self).initialize(app)

    def onPipelineStart(self, ctx):
        super(SassProcessor, self).onPipelineStart(ctx)

        self._map_dir = os.path.join(ctx.tmp_dir, 'sass')
        if ctx.is_main_process:
            if not os.path.isdir(self._map_dir):
                os.makedirs(self._map_dir)

        # Ignore include-only Sass files.
        ctx.ignore_patterns += ['_*.scss', '_*.sass']

    def getDependencies(self, path):
        if _is_include_only(path):
            raise Exception("Include only Sass files should be ignored!")

        map_path = self._getMapPath(path)
        try:
            with open(map_path, 'r') as f:
                dep_map = json.load(f)
        except IOError:
            # Map file not found... rebuild.
            logger.debug("No map file found for Sass file '%s' at '%s'. "
                         "Rebuilding." % (path, map_path))
            return FORCE_BUILD

        if dep_map.get('version') != 3:
            logger.warning("Unknown Sass map version. Rebuilding.")
            return FORCE_BUILD

        sources = dep_map.get('sources', [])
        deps = list(map(_clean_scheme, sources))
        return deps

    def _doProcess(self, in_path, out_path):
        self._ensureInitialized()

        if _is_include_only(in_path):
            raise Exception("Include only Sass files should be ignored!")

        sourcemap = 'none'
        if self.app.cache.enabled:
            sourcemap = 'file'

        args = [self._conf['bin'],
                '--sourcemap=%s' % sourcemap,
                '--style', self._conf['style']]

        cache_dir = self._conf['cache_dir']
        if cache_dir:
            args += ['--cache-location', cache_dir]
        else:
            args += ['--no-cache']

        for lp in self._conf['load_paths']:
            args += ['-I', lp]

        args += self._conf['options']
        args += [in_path, out_path]
        logger.debug("Processing Sass file: %s" % args)

        try:
            retcode = subprocess.call(args)
        except FileNotFoundError as ex:
            logger.error("Tried running Sass processor with command: %s" %
                         args)
            raise Exception("Error running Sass processor. "
                            "Did you install it?") from ex

        # The sourcemap is generated next to the CSS file... there doesn't
        # seem to be any option to override that, sadly... so we need to move
        # it to the cache directory.
        if self.app.cache.enabled:
            src_map_file = out_path + '.map'
            dst_map_file = self._getMapPath(in_path)
            if os.path.exists(dst_map_file):
                os.remove(dst_map_file)
            os.rename(src_map_file, dst_map_file)

        if retcode != 0:
            raise Exception("Error occured in Sass compiler. Please check "
                            "log messages above for more information.")

        return True

    def _ensureInitialized(self):
        if self._conf is not None:
            return

        bin_name = 'scss'
        if platform.system() == 'Windows':
            bin_name += '.cmd'

        self._conf = self.app.config.get('sass') or {}
        self._conf.setdefault('bin', bin_name)
        self._conf.setdefault('style', 'nested')
        self._conf.setdefault('load_paths', [])
        if not isinstance(self._conf['load_paths'], list):
            raise Exception("The `sass/load_paths` configuration setting "
                            "must be an array of paths.")
        self._conf.setdefault('options', [])
        if not isinstance(self._conf['options'], list):
            raise Exception("The `sass/options` configuration setting "
                            "must be an array of arguments.")

        app_root_dir = self.app.root_dir
        load_paths = list(self._conf['load_paths'])
        for i, lp in enumerate(load_paths):
            self._conf['load_paths'][i] = os.path.join(app_root_dir, lp)

        cache_dir = None
        if self.app.cache.enabled:
            cache_dir = os.path.join(self.app.cache_dir, 'sass')
        self._conf.setdefault('cache_dir', cache_dir)

    def _getMapPath(self, path):
        map_name = "%s_%s.map" % (
            os.path.basename(path),
            hashlib.md5(path.encode('utf8')).hexdigest())
        map_path = os.path.join(self._map_dir, map_name)
        return map_path


def _clean_scheme(p):
    if p.startswith('file://'):
        return p[7:]
    return p


def _is_include_only(path):
    name = os.path.basename(path)
    return len(name) > 0 and name[0] == '_'

