from markdown import markdown
from piecrust.formatting.base import Formatter


class MarkdownFormatter(Formatter):
    FORMAT_NAMES = ['markdown', 'mdown', 'md']
    OUTPUT_FORMAT = 'html'

    def render(self, format_name, txt):
        return markdown(txt)

