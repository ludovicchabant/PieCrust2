from piecrust.sources.pageref import PageRef, PageNotFoundError


class Taxonomy(object):
    def __init__(self, app, name, config):
        self.app = app
        self.name = name
        self.term_name = config.get('term', name)
        self.is_multiple = config.get('multiple', False)
        self.page_ref = config.get('page')
        self._source_page_refs = {}

    @property
    def setting_name(self):
        if self.is_multiple:
            return self.name
        return self.term_name

    def resolvePagePath(self, source):
        pr = self.getPageRef(source)
        try:
            return pr.path
        except PageNotFoundError:
            return None

    def getPageRef(self, source):
        if source.name in self._source_page_refs:
            return self._source_page_refs[source.name]

        ref_path = source.getTaxonomyPageRef(self.name)
        page_ref = PageRef(self.app, ref_path)
        self._source_page_refs[source.name] = page_ref
        return page_ref

