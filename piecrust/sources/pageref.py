import re
import os.path


page_ref_pattern = re.compile(r'(?P<src>[\w]+)\:(?P<path>.*?)(;|$)')


class PageNotFoundError(Exception):
    pass


class PageRef(object):
    """ A reference to a page, with support for looking a page in different
        realms.
    """
    def __init__(self, app, page_ref):
        self.app = app
        self._page_ref = page_ref
        self._paths = None
        self._first_valid_path_index = -2
        self._exts = list(app.config.get('site/auto_formats').keys())

    @property
    def exists(self):
        try:
            self._checkPaths()
            return True
        except PageNotFoundError:
            return False

    @property
    def source_name(self):
        self._checkPaths()
        return self._paths[self._first_valid_path_index][0]

    @property
    def source(self):
        return self.app.getSource(self.source_name)

    @property
    def rel_path(self):
        self._checkPaths()
        return self._paths[self._first_valid_path_index][1]

    @property
    def path(self):
        self._checkPaths()
        return self._paths[self._first_valid_path_index][2]

    @property
    def possible_rel_paths(self):
        self._load()
        return [p[1] for p in self._paths]

    @property
    def possible_paths(self):
        self._load()
        return [p[2] for p in self._paths]

    def _load(self):
        if self._paths is not None:
            return

        it = list(page_ref_pattern.finditer(self._page_ref))
        if len(it) == 0:
            raise Exception("Invalid page ref: %s" % self._page_ref)

        self._paths = []
        for m in it:
            source_name = m.group('src')
            source = self.app.getSource(source_name)
            if source is None:
                raise Exception("No such source: %s" % source_name)
            rel_path = m.group('path')
            path = source.resolveRef(rel_path)
            if '%ext%' in rel_path:
                for e in self._exts:
                    self._paths.append(
                            (source_name,
                             rel_path.replace('%ext%', e),
                             path.replace('%ext%', e)))
            else:
                self._paths.append((source_name, rel_path, path))

    def _checkPaths(self):
        if self._first_valid_path_index >= 0:
            return
        if self._first_valid_path_index == -1:
            raise PageNotFoundError(
                    "No valid paths were found for page reference: %s" %
                    self._page_ref)

        self._load()
        self._first_valid_path_index = -1
        for i, path_info in enumerate(self._paths):
            if os.path.isfile(path_info[2]):
                self._first_valid_path_index = i
                break

