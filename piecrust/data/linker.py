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
            self._ensureParentGroup()

            src = self._source
            app = src.app

            cur_group = self._parent_group
            self._ancestors = []
            while cur_group:
                pi = src.getRelatedContents(cur_group,
                                            REL_LOGICAL_PARENT_ITEM)
                if pi is not None:
                    pipage = app.getPage(src, pi)
                    self._ancestors.append(PaginationData(pipage))
                    cur_group = src.getParentGroup(pi)
                else:
                    break
        return self._ancestors

    @property
    def siblings(self):
        if self._siblings is None:
            self._ensureParentGroup()

            src = self._source
            app = src.app

            self._siblings = []
            for i in src.getContents(self._parent_group):
                if not i.is_group:
                    ipage = app.getPage(src, i)
                    self._siblings.append(PaginationData(ipage))
        return self._siblings

    @property
    def children(self):
        if self._children is None:
            src = self._source
            app = src.app

            self._children = []
            child_group = src.getRelatedContents(self._content_item,
                                                 REL_LOGICAl_CHILD_GROUP)
            if child_group:
                for i in src.getContents(child_group):
                    ipage = app.getPage(src, i)
                    self._children.append(PaginationData(ipage))
        return self._children

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

    def _ensureParentGroup(self):
        if self._parent_group is _unloaded:
            src = self._source
            item = self._content_item
            self._parent_group = src.getParentGroup(item)

    def _debugRenderAncestors(self):
        return [i.title for i in self.ancestors]

    def _debugRenderSiblings(self):
        return [i.title for i in self.siblings]

    def _debugRenderChildren(self):
        return [i.title for i in self.children]

