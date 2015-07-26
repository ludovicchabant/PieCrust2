import yaml
from pygments.formatters import HtmlFormatter
from piecrust.processing.base import SimpleFileProcessor


class PygmentsStyleProcessor(SimpleFileProcessor):
    PROCESSOR_NAME = 'pygments_style'

    def __init__(self):
        super(PygmentsStyleProcessor, self).__init__({'pygstyle': 'css'})

    def _doProcess(self, in_path, out_path):
        with open(in_path, 'r') as fp:
            config = yaml.load(fp)

        style_name = config.get('style', 'default')
        class_name = config.get('class', '.highlight')
        fmt = HtmlFormatter(style=style_name).get_style_defs(class_name)

        with open(out_path, 'w') as fp:
            fp.write(fmt)

        return True

