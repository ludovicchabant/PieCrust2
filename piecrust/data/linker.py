import logging
from piecrust.data.paginationdata import PaginationData
from piecrust.sources.base import (
    REL_PARENT_GROUP, REL_LOGICAL_PARENT_ITEM, REL_LOGICAL_CHILD_GROUP)


logger = logging.getLogger(__name__)


_unloaded = object()


class Linker:
    """ A template-exposed data class that lets the user navigate the
        logical hierarchy of pages in a page source.
    """
    debug_render = ['parent', 'ancestors', 'siblings', 'children', 'root',
                    'forpath']
    debug_render_invoke = ['ancestors', 'siblings', 'children']
    debug_render_redirect = {
        'ancestors': '_debugRenderAncestors',
        'siblings': '_debugRenderSiblings',
        'children': '_debugRenderChildren'}

    def __init__(self, source, content_item):
        self._source = source
        self._content_item = content_item

        self._parent_group = _unloaded
        self._ancestors = None
        self._siblings = None
        self._children = None

    @property
    def parent(self):
        a = self.ancestors
        if a:
            return a[0]
        return None

    @property
    def root(self):
        a = self.ancestors
        if a:
            return a[-1]
        return self.myself

    @property
    def myself(self):
        page = self._source.app.getPage(self._source, self._content_item)
        return self._makePageData(page)

    @property
    def ancestors(self):
        if self._ancestors is None:
            src = self._source
            app = src.app

            self._ancestors = []
            cur_group = self._getParentGroup()
            while cur_group:
                pi = src.getRelatedContents(cur_group,
                                            REL_LOGICAL_PARENT_ITEM)
                if pi is not None:
                    pipage = app.getPage(src, pi)
                    self._ancestors.append(self._makePageData(pipage))
                    cur_group = src.getRelatedContents(
                        pi, REL_PARENT_GROUP)
                else:
                    break
        return self._ancestors

    @property
    def siblings(self):
        src = self._source
        app = src.app
        sibs = []
        for i in self._getAllSiblings():
            if not i.is_group:
                ipage = app.getPage(src, i)
                ipage_data = self._makePageData(ipage)
                sibs.append(ipage_data)
        return sibs

    @property
    def siblings_all(self):
        src = self._source
        app = src.app
        sibs = []
        for i in self._getAllSiblings():
            if not i.is_group:
                ipage = app.getPage(src, i)
                ipage_data = self._makePageData(ipage)
                sibs.append(ipage_data)
            else:
                sibs.append(self._makeGroupData(i))
        return sibs

    @property
    def has_children(self):
        return bool(self._getAllChildren())

    @property
    def children(self):
        src = self._source
        app = src.app
        childs = []
        for i in self._getAllChildren():
            if not i.is_group:
                ipage = app.getPage(src, i)
                childs.append(self._makePageData(ipage))
        return childs

    @property
    def children_all(self):
        src = self._source
        app = src.app
        childs = []
        for i in self._getAllChildren():
            if not i.is_group:
                ipage = app.getPage(src, i)
                childs.append(self._makePageData(ipage))
            else:
                childs.append(self._makeGroupData(i))
        return childs

    def forpath(self, path):
        # TODO: generalize this for sources that aren't file-system based.
        item = self._source.findContentFromRoute({'slug': path})
        return Linker(self._source, item)

    def childrenof(self, path, with_groups=False):
        # TODO: generalize this for sources that aren't file-system based.
        src = self._source
        app = src.app
        item = src.findContentFromRoute({'slug': path})
        if item is None:
            raise ValueError("No such content: %s" % path)

        group = self._source.getRelatedContents(item,
                                                REL_LOGICAL_CHILD_GROUP)
        if group is not None:
            childs = []
            for i in src.getContents(group):
                if not i.is_group:
                    ipage = app.getPage(src, i)
                    childs.append(self._makePageData(ipage))
                elif with_groups:
                    childs.append(self._makeGroupData(i))
            return childs
        return None

    def _getAllSiblings(self):
        if self._siblings is None:
            self._siblings = list(self._source.getContents(
                self._getParentGroup()))
        return self._siblings

    def _getAllChildren(self):
        if self._children is None:
            child_group = self._source.getRelatedContents(
                self._content_item, REL_LOGICAL_CHILD_GROUP)
            if child_group is not None:
                self._children = list(
                    self._source.getContents(child_group))
            else:
                self._children = []
        return self._children

    def _getParentGroup(self):
        if self._parent_group is _unloaded:
            self._parent_group = self._source.getRelatedContents(
                self._content_item, REL_PARENT_GROUP)
        return self._parent_group

    def _makePageData(self, page):
        is_self = page.content_spec == self._content_item.spec
        return _PageData(page, is_self)

    def _makeGroupData(self, group):
        return _GroupData(self._source, group)

    def _debugRenderAncestors(self):
        return [i.title for i in self.ancestors]

    def _debugRenderSiblings(self):
        return [i.title for i in self.siblings]

    def _debugRenderChildren(self):
        return [i.title for i in self.children]


class _PageData(PaginationData):
    def __init__(self, page, is_self):
        super().__init__(page)
        self.is_self = is_self
        self.is_page = True

    def _load(self):
        super()._load()
        self._mapLoader('is_dir', lambda d, n: self.family.has_children)
        self._mapLoader('is_group', lambda d, n: self.family.has_children)


class _GroupData:
    def __init__(self, source, group_item):
        self._source = source
        self._group_item = group_item
        self.is_page = False
        self.is_dir = True
        self.is_group = True
        self.family = Linker(source, group_item)
