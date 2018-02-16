import time
import collections.abc
from piecrust.dataproviders.base import DataProvider
from piecrust.dataproviders.pageiterator import PageIterator
from piecrust.sources.list import ListSource
from piecrust.sources.taxonomy import Taxonomy


class BlogDataProvider(DataProvider, collections.abc.Mapping):
    PROVIDER_NAME = 'blog'

    debug_render_doc = """Provides a list of blog posts and yearly/monthly
                          archives."""
    debug_render_dynamic = (['_debugRenderTaxonomies'] +
                            DataProvider.debug_render_dynamic)

    def __init__(self, source, page):
        super().__init__(source, page)
        self._posts = None
        self._yearly = None
        self._monthly = None
        self._taxonomies = {}
        self._archives_built = False
        self._ctx_set = False

    def _addSource(self, source):
        raise Exception("The blog data provider doesn't support "
                        "combining multiple sources.")

    @property
    def posts(self):
        self._buildPosts()
        # Reset each time on access in case a page is showing 2 different
        # lists of the same blog.
        self._posts.reset()
        return self._posts

    @property
    def years(self):
        self._buildArchives()
        return self._yearly

    @property
    def months(self):
        self._buildArchives()
        return self._monthly

    @property
    def taxonomies(self):
        return list(self._app.config.get('site/taxonomies').keys())

    def __getitem__(self, name):
        if name in ['posts', 'years', 'months', 'taxonomies']:
            return getattr(self, name)

        self._buildArchives()
        return self._taxonomies[name]

    def __getattr__(self, name):
        self._buildArchives()
        try:
            return self._taxonomies[name]
        except KeyError:
            raise AttributeError("No such taxonomy: %s" % name)

    def __len__(self):
        return 4 + len(self.taxonomies)

    def __iter__(self):
        yield 'posts'
        yield 'years'
        yield 'months'
        yield 'taxonomies'
        yield from self.taxonomies

    def _debugRenderTaxonomies(self):
        return self.taxonomies

    def _buildPosts(self):
        if self._posts is None:
            it = PageIterator(self._sources[0], current_page=self._page)
            self._onIteration()
            self._posts = it

    def _buildArchives(self):
        if self._archives_built:
            return

        yearly_index = {}
        monthly_index = {}
        tax_index = {}

        taxonomies = []
        tax_names = list(self._app.config.get('site/taxonomies').keys())
        for tn in tax_names:
            tax_cfg = self._app.config.get('site/taxonomies/' + tn)
            taxonomies.append(Taxonomy(tn, tax_cfg))
            tax_index[tn] = {}

        page = self._page
        source = self._sources[0]

        for post in source.getAllPages():
            post_dt = post.datetime

            year = post_dt.year
            month = (post_dt.month, post_dt.year)

            posts_this_year = yearly_index.get(year)
            if posts_this_year is None:
                timestamp = time.mktime(
                    (post_dt.year, 1, 1, 0, 0, 0, 0, 0, -1))
                posts_this_year = BlogArchiveEntry(
                    source, page, year, timestamp)
                yearly_index[year] = posts_this_year
            posts_this_year._items.append(post.content_item)

            posts_this_month = monthly_index.get(month)
            if posts_this_month is None:
                timestamp = time.mktime(
                    (post_dt.year, post_dt.month, 1,
                     0, 0, 0, 0, 0, -1))
                posts_this_month = BlogArchiveEntry(
                    source, page, month[0], timestamp)
                monthly_index[month] = posts_this_month
            posts_this_month._items.append(post.content_item)

            for tax in taxonomies:
                post_term = post.config.get(tax.setting_name)
                if post_term is None:
                    continue

                posts_this_tax = tax_index[tax.name]
                if tax.is_multiple:
                    for val in post_term:
                        entry = posts_this_tax.get(val)
                        if entry is None:
                            entry = BlogTaxonomyEntry(source, page, val)
                            posts_this_tax[val] = entry
                        entry._items.append(post.content_item)
                else:
                    entry = posts_this_tax.get(val)
                    if entry is None:
                        entry = BlogTaxonomyEntry(source, page, post_term)
                        posts_this_tax[val] = entry
                    entry._items.append(post.content_item)

        self._yearly = list(sorted(
            yearly_index.values(),
            key=lambda e: e.timestamp, reverse=True))
        self._monthly = list(sorted(
            monthly_index.values(),
            key=lambda e: e.timestamp, reverse=True))

        self._taxonomies = {}
        for tax_name, entries in tax_index.items():
            self._taxonomies[tax_name] = list(
                sorted(entries.values(), key=lambda i: i.term))

        self._onIteration()

        self._archives_built = True

    def _onIteration(self):
        if not self._ctx_set:
            rcs = self._app.env.render_ctx_stack
            if rcs.current_ctx:
                rcs.current_ctx.addUsedSource(self._sources[0])
            self._ctx_set = True


class BlogArchiveEntry:
    debug_render = ['name', 'timestamp', 'posts']
    debug_render_invoke = ['name', 'timestamp', 'posts']

    def __init__(self, source, page, name, timestamp):
        self.name = name
        self.timestamp = timestamp
        self._source = source
        self._page = page
        self._items = []
        self._iterator = None

    def __str__(self):
        return str(self.name)

    def __int__(self):
        return int(self.name)

    @property
    def posts(self):
        self._load()
        self._iterator.reset()
        return self._iterator

    def _load(self):
        if self._iterator is not None:
            return

        src = ListSource(self._source, self._items)
        self._iterator = PageIterator(src, current_page=self._page)


class BlogTaxonomyEntry:
    debug_render = ['name', 'post_count', 'posts']
    debug_render_invoke = ['name', 'post_count', 'posts']

    def __init__(self, source, page, term):
        self.term = term
        self._source = source
        self._page = page
        self._items = []
        self._iterator = None

    def __str__(self):
        return self.term

    @property
    def name(self):
        return self.term

    @property
    def posts(self):
        self._load()
        self._iterator.reset()
        return self._iterator

    @property
    def post_count(self):
        return len(self._items)

    def _load(self):
        if self._iterator is not None:
            return

        src = ListSource(self._source, self._items)
        self._iterator = PageIterator(src, current_page=self._page)

