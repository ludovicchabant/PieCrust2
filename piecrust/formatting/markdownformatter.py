from piecrust.formatting.base import Formatter


class MarkdownFormatter(Formatter):
    FORMAT_NAMES = ['markdown', 'mdown', 'md']
    OUTPUT_FORMAT = 'html'

    def __init__(self):
        super(MarkdownFormatter, self).__init__()
        self._formatter = None

    def render(self, format_name, txt):
        assert format_name in self.FORMAT_NAMES
        self._ensureInitialized()
        return self._formatter.reset().convert(txt)

    def _ensureInitialized(self):
        if self._formatter is not None:
            return

        config = self.app.config.get('markdown')
        if config is None:
            config = {}
        elif not isinstance(config, dict):
            raise Exception("The `markdown` configuration setting must be "
                            "a dictionary.")

        extensions = config.get('extensions', [])
        if isinstance(extensions, str):
            extensions = [e.strip() for e in extensions.split(',')]
        # Compatibility with PieCrust 1.x
        if config.get('use_markdown_extra'):
            extensions.append('extra')

        extension_configs = config.get('extension_configs', {})

        from markdown import Markdown
        self._formatter = Markdown(extensions=extensions,
                                   extension_configs=extension_configs)
