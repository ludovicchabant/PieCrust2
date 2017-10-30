import logging
from piecrust.data.paginationdata import PaginationData
from piecrust.sources.base import (
    REL_PARENT_GROUP, REL_LOGICAL_PARENT_ITEM, REL_LOGICAl_CHILD_GROUP)


logger = logging.getLogger(__name__)


_unloaded = object()


class Linker:
    """ A template-exposed data class that lets the user navigate the
        logical hierarchy of pages in a page source.
    """
    debug_render = ['parent', 'ancestors', 'siblings', 'children', 'root',
                    'forpath']
    debug_render_invoke = ['parent', 'ancestors', 'siblings', 'children',
                           'root']
    debug_render_redirect = {
        'ancestors': '_debugRenderAncestors',
        'siblings': '_debugRenderSiblings',
        'children': '_debugRenderChildren',
        'root': '_debugRenderRoot'}

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
                    self._ancestors.append(PaginationData(pipage))
                    cur_group = src.getRelatedContents(
                        pi, REL_PARENT_GROUP)
                else:
                    break
        return self._ancestors

    @property
    def siblings(self):
        src = self._source
        app = src.app
        for i in self._getAllSiblings():
            if not i.is_group:
                ipage = app.getPage(src, i)
                ipage_data = PaginationData(ipage)
                ipage_data._setValue('is_self',
                                     i.spec == self._content_item.spec)
                yield ipage_data

    @property
    def children(self):
        src = self._source
        app = src.app
        for i in self._getAllChildren():
            if not i.is_group:
                ipage = app.getPage(src, i)
                yield PaginationData(ipage)

    def forpath(self, path):
        # TODO: generalize this for sources that aren't file-system based.
        item = self._source.findContent({'slug': path})
        return Linker(self._source, item)

    def childrenof(self, path):
        # TODO: generalize this for sources that aren't file-system based.
        src = self._source
        app = src.app
        group = src.findGroup(path)
        if group is not None:
            for i in src.getContents(group):
                if not i.is_group:
                    ipage = app.getPage(src, i)
                    yield PaginationData(ipage)
        return None

    def _getAllSiblings(self):
        if self._siblings is None:
            self._siblings = list(self._source.getContents(
                self._getParentGroup()))
        return self._siblings

    def _getAllChildren(self):
        if self._children is None:
            child_group = self._source.getRelatedContents(
                self._content_item, REL_LOGICAl_CHILD_GROUP)
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

    def _debugRenderAncestors(self):
        return [i.title for i in self.ancestors]

    def _debugRenderSiblings(self):
        return [i.title for i in self.siblings]

    def _debugRenderChildren(self):
        return [i.title for i in self.children]

