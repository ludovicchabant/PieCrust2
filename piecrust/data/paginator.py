import math
import logging
from werkzeug.utils import cached_property
from piecrust.data.filters import PaginationFilter, page_value_accessor
from piecrust.data.iterators import PageIterator
from piecrust.sources.interfaces import IPaginationSource


logger = logging.getLogger(__name__)


class Paginator(object):
    debug_render = [
            'has_more', 'items', 'has_items', 'items_per_page',
            'items_this_page', 'prev_page_number', 'this_page_number',
            'next_page_number', 'prev_page', 'next_page',
            'total_item_count', 'total_page_count',
            'next_item', 'prev_item']
    debug_render_invoke = [
            'has_more', 'items', 'has_items', 'items_per_page',
            'items_this_page', 'prev_page_number', 'this_page_number',
            'next_page_number', 'prev_page', 'next_page',
            'total_item_count', 'total_page_count',
            'next_item', 'prev_item']

    def __init__(self, qualified_page, source, *,
                 page_num=1, pgn_filter=None, items_per_page=-1):
        self._parent_page = qualified_page
        self._source = source
        self._page_num = page_num
        self._iterator = None
        self._pgn_filter = pgn_filter
        self._items_per_page = items_per_page
        self._pgn_set_on_ctx = False

    @property
    def is_loaded(self):
        return self._iterator is not None

    @property
    def has_more(self):
        return self.next_page_number is not None

    @property
    def unload(self):
        self._iterator = None

    # Backward compatibility with PieCrust 1.0 {{{
    @property
    def posts(self):
        return self.items

    @property
    def has_posts(self):
        return self.has_items

    @property
    def posts_per_page(self):
        return self.items_per_page

    @property
    def posts_this_page(self):
        return self.items_this_page

    @property
    def total_post_count(self):
        return self.total_item_count

    @property
    def next_post(self):
        return self.next_item

    @property
    def prev_post(self):
        return self.prev_item
    # }}}

    @property
    def items(self):
        self._load()
        return self._iterator

    @property
    def has_items(self):
        return self.posts_this_page > 0

    @cached_property
    def items_per_page(self):
        if self._items_per_page > 0:
            return self._items_per_page
        if self._parent_page:
            ipp = self._parent_page.config.get('items_per_page')
            if ipp is not None:
                return ipp
        if isinstance(self._source, IPaginationSource):
            return self._source.getItemsPerPage()
        raise Exception("No way to figure out how many items to display "
                        "per page.")

    @property
    def items_this_page(self):
        self._load()
        return len(self._iterator)

    @property
    def prev_page_number(self):
        if self._page_num > 1:
            return self._page_num - 1
        return None

    @property
    def this_page_number(self):
        return self._page_num

    @property
    def next_page_number(self):
        self._load()
        if self._iterator._has_more:
            return self._page_num + 1
        return None

    @property
    def prev_page(self):
        num = self.prev_page_number
        if num is not None:
            return self._getPageUri(num)
        return None

    @property
    def this_page(self):
        return self._getPageUri(self._page_num)

    @property
    def next_page(self):
        num = self.next_page_number
        if num is not None:
            return self._getPageUri(num)
        return None

    @property
    def total_item_count(self):
        self._load()
        return self._iterator.total_count

    @property
    def total_page_count(self):
        total_count = self.total_item_count
        per_page = self.items_per_page
        return int(math.ceil(total_count / per_page))

    @property
    def next_item(self):
        self._load()
        return self._iterator.prev_page

    @property
    def prev_item(self):
        self._load()
        return self._iterator.next_page

    def all_page_numbers(self, radius=-1):
        total_page_count = self.total_page_count
        if total_page_count == 0:
            return []

        if radius <= 0 or total_page_count < (2 * radius + 1):
            return list(range(1, total_page_count + 1))

        first_num = self._page_num - radius
        last_num = self._page_num + radius
        if first_num <= 0:
            last_num += 1 - first_num
            first_num = 1
        elif last_num > total_page_count:
            first_num -= (last_num - total_page_count)
            last_num = total_page_count
        first_num = max(1, first_num)
        last_num = min(total_page_count, last_num)
        return list(range(first_num, last_num + 1))

    def page(self, index):
        return self._getPageUri(index)

    def _load(self):
        if self._iterator is not None:
            return

        if self._source is None:
            raise Exception("Can't load pagination data: no source has "
                            "been defined.")

        pag_filter = self._getPaginationFilter()
        offset = (self._page_num - 1) * self.items_per_page
        self._iterator = PageIterator(
                self._source,
                current_page=self._parent_page,
                pagination_filter=pag_filter,
                offset=offset, limit=self.items_per_page,
                locked=True)
        self._iterator._iter_event += self._onIteration

    def _getPaginationFilter(self):
        f = PaginationFilter(value_accessor=page_value_accessor)

        if self._pgn_filter is not None:
            f.addClause(self._pgn_filter.root_clause)

        if isinstance(self._source, IPaginationSource):
            sf = self._source.getPaginationFilter(self._parent_page)
            if sf is not None:
                f.addClause(sf.root_clause)

        return f

    def _getPageUri(self, index):
        return self._parent_page.getUri(index)

    def _onIteration(self):
        if self._parent_page is not None and not self._pgn_set_on_ctx:
            eis = self._parent_page.app.env.exec_info_stack
            eis.current_page_info.render_ctx.setPagination(self)
            self._pgn_set_on_ctx = True

