import logging
from piecrust.data.paginationdata import PaginationData
from piecrust.sources.base import (
    REL_LOGICAL_PARENT_ITEM, REL_LOGICAl_CHILD_GROUP)


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

    def __init__(self, page):
        self._page = page
        self._content_item = page.content_item
        self._source = page.source
        self._app = page.app

        self._parent = _unloaded
        self._ancestors = None
        self._siblings = None
        self._children = None

    @property
    def parent(self):
        if self._parent is _unloaded:
            pi = self._source.getRelatedContents(self._content_item,
                                                 REL_LOGICAL_PARENT_ITEM)
            if pi is not None:
                pipage = self._app.getPage(self._source, pi)
                self._parent = PaginationData(pipage)
            else:
                self._parent = None
        return self._parent

    @property
    def ancestors(self):
        if self._ancestors is None:
            cur_item = self._content_item
            self._ancestors = []
            while True:
                pi = self._source.getRelatedContents(
                    cur_item, REL_LOGICAL_PARENT_ITEM)
                if pi is not None:
                    pipage = self._app.getPage(self._source, pi)
                    self._ancestors.append(PaginationData(pipage))
                    cur_item = pi
                else:
                    break
        return self._ancestors

    @property
    def siblings(self):
        if self._siblings is None:
            self._siblings = []
            parent_group = self._source.getParentGroup(self._content_item)
            for i in self._source.getContents(parent_group):
                if not i.is_group:
                    ipage = self._app.getPage(self._source, i)
                    self._siblings.append(PaginationData(ipage))
        return self._siblings

    @property
    def children(self):
        if self._children is None:
            self._children = []
            child_group = self._source.getRelatedContents(
                self._content_item, REL_LOGICAl_CHILD_GROUP)
            if child_group:
                for i in self._source.getContents(child_group):
                    ipage = self._app.getPage(self._source, i)
                    self._children.append(PaginationData(ipage))
        return self._children

    def _debugRenderAncestors(self):
        return [i.name for i in self.ancestors]

    def _debugRenderSiblings(self):
        return [i.name for i in self.siblings]

    def _debugRenderChildren(self):
        return [i.name for i in self.children]

    def _debugRenderRoot(self):
        r = self.root
        if r is not None:
            return r.name
        return None

