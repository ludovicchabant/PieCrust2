import logging
from piecrust.formatting.base import Formatter


logger = logging.getLogger(__name__)


class HoedownFormatter(Formatter):
    FORMAT_NAMES = ['markdown', 'mdown', 'md']
    OUTPUT_FORMAT = 'html'

    def __init__(self):
        super(HoedownFormatter, self).__init__()
        self._formatter = None

    def render(self, format_name, txt):
        assert format_name in self.FORMAT_NAMES
        self._ensureInitialized()
        return self._formatter(txt)

    def _ensureInitialized(self):
        if self._formatter is not None:
            return

        import misaka

        # Don't show warnings once for each worker when baking, so only
        # show them for the first. If the variable is not set, we're not
        # baking so do show them either way.
        show_warnings = (self.app.config.get('baker/worker_id', 0) == 0)

        config = self.app.config.get('hoedown')
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            raise Exception("The `hoedown` configuration setting must be "
                            "a dictionary.")

        extensions = config.get('extensions', [])
        if isinstance(extensions, str):
            extensions = [e.strip() for e in extensions.split(',')]
        # Compatibility with PieCrust 1.x
        if config.get('use_markdown_extra'):
            extensions.append('extra')

        render_flags = config.get('render_flags')
        if render_flags is None:
            render_flags = []

        # Translate standard Markdown formatter extensions to Hoedown
        # extension/render flags to make it easier to use Hoedown as a drop-in
        # replacement.
        exts = 0
        rdrf = 0
        other = 0
        for n in extensions:
            # Try an extension?
            e = getattr(misaka, 'EXT_' + n.upper(), None)
            if e is not None:
                exts |= e
                continue

            # Try a render flag?
            f = getattr(misaka, 'HTML_' + n.upper(), None)
            if f is not None:
                rdrf |= f

            # Other flag?
            f = getattr(misaka, 'TABLE_' + n.upper(), None)
            if f is not None:
                other |= f

            # Try translating from a Markdown extension name.
            t = ext_translate.get(n)
            if t is None:
                if show_warnings:
                    logger.warning("Unknown Hoedown Markdown extension or flag: "
                                   "%s" % n)
                continue
            if not isinstance(t, list):
                t = [t]
            for i in t:
                if i.startswith('EXT_'):
                    exts |= getattr(misaka, i)
                elif i.startswith('HTML_'):
                    rdrf |= getattr(misaka, i)
                elif show_warnings:
                    logger.warning("Unknown Hoedown Markdown extension or flag:"
                                   "%s" % n)
            if n == 'extra' and show_warnings:
                # Special warning for the 'extra' extension.
                logger.warning(
                    "The 'extra' extension doesn't have a full equivalent "
                    "in Hoedown Markdown. Only 'fenced_code', 'footnotes' and "
                    "'tables' extensions will be active. "
                    "To remove this warning, replace 'extra' with those 3 "
                    "specific extensions.")

        # Enable a few things by default.
        exts |= misaka.EXT_NO_INTRA_EMPHASIS

        renderer = misaka.HtmlRenderer(flags=rdrf)
        self._formatter = misaka.Markdown(renderer, extensions=(exts | other))


ext_translate = {
        'fenced_code': 'EXT_FENCED_CODE',
        'footnotes': 'EXT_FOOTNOTES',
        'tables': 'EXT_TABLES',
        'nl2br': 'HTML_HARD_WRAP',
        'smarty': 'HTML_SMARTYPANTS',
        'smartypants': 'HTML_SMARTYPANTS',
        'toc': 'HTML_TOC',
        'extra': ['EXT_FENCED_CODE', 'EXT_FOOTNOTES', 'EXT_TABLES']
        }

