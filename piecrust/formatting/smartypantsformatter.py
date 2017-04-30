from piecrust.formatting.base import Formatter, PRIORITY_LAST


class SmartyPantsFormatter(Formatter):
    FORMAT_NAMES = ['html']
    OUTPUT_FORMAT = 'html'

    def __init__(self):
        super(SmartyPantsFormatter, self).__init__()
        self.priority = PRIORITY_LAST

        import smartypants
        self._sp = smartypants.smartypants

    def initialize(self, app):
        super(SmartyPantsFormatter, self).initialize(app)
        self.enabled = (
            app.config.get('smartypants/enable') or
            app.config.get('smartypants/enabled'))

    def render(self, format_name, txt):
        assert format_name == 'html'
        return self._sp(txt)
