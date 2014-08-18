from markdown import markdown
from piecrust.formatting.base import Formatter


class MarkdownFormatter(Formatter):
    FORMAT_NAMES = ['markdown', 'mdown', 'md']
    OUTPUT_FORMAT = 'html'

    def __init__(self):
        super(MarkdownFormatter, self).__init__()
        self._extensions = None

    def render(self, format_name, txt):
        self._ensureInitialized()
        return markdown(txt, extensions=self._extensions)

    def _ensureInitialized(self):
        if self._extensions is not None:
            return

        extensions = self.app.config.get('markdown/extensions')
        if extensions is None:
            extensions = []
        # Compatibility with PieCrust 1.x
        if self.app.config.get('markdown/use_markdown_extra'):
            extensions.append('extra')
        self._extensions = extensions

