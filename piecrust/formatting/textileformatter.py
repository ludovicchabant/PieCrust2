from piecrust.formatting.base import Formatter


class TextileFormatter(Formatter):
    FORMAT_NAMES = ['textile', 'text']
    OUTPUT_FORMAT = 'html'

    def render(self, format_name, text):
        from textile import textile
        assert format_name in self.FORMAT_NAMES
        return textile(text)

