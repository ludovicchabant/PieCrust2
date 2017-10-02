import os.path
from jinja2 import FileSystemLoader


class PieCrustLoader(FileSystemLoader):
    def __init__(self, searchpath, encoding='utf-8'):
        super(PieCrustLoader, self).__init__(searchpath, encoding)
        self.segments_cache = {}

    def get_source(self, environment, template):
        if template.startswith('$seg='):
            filename, seg_content = self.segments_cache[template]

            mtime = os.path.getmtime(filename)

            def uptodate():
                try:
                    return os.path.getmtime(filename) == mtime
                except OSError:
                    return False

            return seg_content, filename, uptodate

        return super(PieCrustLoader, self).get_source(environment, template)
