import os.path
import logging
from piecrust.environment import AbortedSourceUseError
from piecrust.templating.base import (TemplateEngine, TemplateNotFoundError,
                                      TemplatingError)


logger = logging.getLogger(__name__)


class JinjaTemplateEngine(TemplateEngine):
    # Name `twig` is for backwards compatibility with PieCrust 1.x.
    ENGINE_NAMES = ['jinja', 'jinja2', 'j2', 'twig']
    EXTENSIONS = ['html', 'jinja', 'jinja2', 'j2', 'twig']

    def __init__(self):
        self.env = None
        self._jinja_syntax_error = None
        self._jinja_not_found = None

    def renderSegmentPart(self, path, seg_part, data):
        self._ensureLoaded()

        if not _string_needs_render(seg_part.content):
            return seg_part.content

        part_path = _make_segment_part_path(path, seg_part.offset)
        self.env.loader.segment_parts_cache[part_path] = (
            path, seg_part.content)
        try:
            tpl = self.env.get_template(part_path)
        except self._jinja_syntax_error as tse:
            raise self._getTemplatingError(tse, filename=path)
        except self._jinja_not_found:
            raise TemplateNotFoundError()

        try:
            return tpl.render(data)
        except self._jinja_syntax_error as tse:
            raise self._getTemplatingError(tse)
        except AbortedSourceUseError:
            raise
        except Exception as ex:
            if self.app.debug:
                raise
            msg = "Error rendering Jinja markup"
            rel_path = os.path.relpath(path, self.app.root_dir)
            raise TemplatingError(msg, rel_path) from ex

    def renderFile(self, paths, data):
        self._ensureLoaded()
        tpl = None
        logger.debug("Looking for template: %s" % paths)
        rendered_path = None
        for p in paths:
            try:
                tpl = self.env.get_template(p)
                rendered_path = p
                break
            except self._jinja_syntax_error as tse:
                raise self._getTemplatingError(tse)
            except self._jinja_not_found:
                pass

        if tpl is None:
            raise TemplateNotFoundError()

        try:
            return tpl.render(data)
        except self._jinja_syntax_error as tse:
            raise self._getTemplatingError(tse)
        except AbortedSourceUseError:
            raise
        except Exception as ex:
            msg = "Error rendering Jinja markup"
            rel_path = os.path.relpath(rendered_path, self.app.root_dir)
            raise TemplatingError(msg, rel_path) from ex

    def _getTemplatingError(self, tse, filename=None):
        filename = tse.filename or filename
        if filename and os.path.isabs(filename):
            filename = os.path.relpath(filename, self.env.app.root_dir)
        err = TemplatingError(str(tse), filename, tse.lineno)
        raise err from tse

    def _ensureLoaded(self):
        if self.env:
            return

        # Get the list of extensions to load.
        ext_names = self.app.config.get('jinja/extensions', [])
        if not isinstance(ext_names, list):
            ext_names = [ext_names]

        # Turn on autoescape by default.
        autoescape = self.app.config.get('twig/auto_escape')
        if autoescape is not None:
            logger.warning("The `twig/auto_escape` setting is now called "
                           "`jinja/auto_escape`.")
        else:
            autoescape = self.app.config.get('jinja/auto_escape', True)
        if autoescape:
            ext_names.append('autoescape')

        # Create the final list of extensions.
        from piecrust.templating.jinja.extensions import (
            PieCrustHighlightExtension, PieCrustCacheExtension,
            PieCrustSpacelessExtension, PieCrustFormatExtension)
        extensions = [
            PieCrustHighlightExtension,
            PieCrustCacheExtension,
            PieCrustSpacelessExtension,
            PieCrustFormatExtension]
        for n in ext_names:
            if '.' not in n:
                n = 'jinja2.ext.' + n
            extensions.append(n)
        for je in self.app.plugin_loader.getTemplateEngineExtensions('jinja'):
            extensions.append(je)

        # Create the Jinja environment.
        logger.debug("Creating Jinja environment with folders: %s" %
                     self.app.templates_dirs)
        from piecrust.templating.jinja.loader import PieCrustLoader
        loader = PieCrustLoader(self.app.templates_dirs)
        from piecrust.templating.jinja.environment import PieCrustEnvironment
        self.env = PieCrustEnvironment(
            self.app,
            loader=loader,
            extensions=extensions)

        # Get types we need later.
        from jinja2 import TemplateNotFound
        from jinja2.exceptions import TemplateSyntaxError
        self._jinja_syntax_error = TemplateSyntaxError
        self._jinja_not_found = TemplateNotFound


def _string_needs_render(txt):
    index = txt.find('{')
    while index >= 0:
        ch = txt[index + 1]
        if ch == '{' or ch == '%':
            return True
        index = txt.find('{', index + 1)
    return False


def _make_segment_part_path(path, start):
    return '$part=%s:%d' % (path, start)


