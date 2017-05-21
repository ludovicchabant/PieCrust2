import time
import collections.abc
from piecrust.dataproviders.base import DataProvider
from piecrust.generation.taxonomy import Taxonomy


class BlogDataProvider(DataProvider, collections.abc.Mapping):
    PROVIDER_NAME = 'blog'

    debug_render_doc = """Provides a list of blog posts and yearly/monthly
                          archives."""
    debug_render_dynamic = (['_debugRenderTaxonomies'] +
                            DataProvider.debug_render_dynamic)

    def __init__(self, source, page, override):
        super(BlogDataProvider, self).__init__(source, page, override)
        self._yearly = None
        self._monthly = None
        self._taxonomies = {}
        self._ctx_set = False

    @property
    def posts(self):
        return self._posts()

    @property
    def years(self):
        return self._buildYearlyArchive()

    @property
    def months(self):
        return self._buildMonthlyArchive()

    def __getitem__(self, name):
        if name == 'posts':
            return self._posts()
        elif name == 'years':
            return self._buildYearlyArchive()
        elif name == 'months':
            return self._buildMonthlyArchive()

        if self._source.app.config.get('site/taxonomies/' + name) is not None:
            return self._buildTaxonomy(name)

        raise KeyError("No such item: %s" % name)

    def __iter__(self):
        keys = ['posts', 'years', 'months']
        keys += list(self._source.app.config.get('site/taxonomies').keys())
        return iter(keys)

    def __len__(self):
        return 3 + len(self._source.app.config.get('site/taxonomies'))

    def _debugRenderTaxonomies(self):
        return list(self._source.app.config.get('site/taxonomies').keys())

    def _posts(self):
        it = PageIterator(self._source, current_page=self._page)
        it._iter_event += self._onIteration
        return it

    def _buildYearlyArchive(self):
        if self._yearly is not None:
            return self._yearly

        self._yearly = []
        yearly_index = {}
        for post in self._source.getPages():
            year = post.datetime.strftime('%Y')

            posts_this_year = yearly_index.get(year)
            if posts_this_year is None:
                timestamp = time.mktime(
                        (post.datetime.year, 1, 1, 0, 0, 0, 0, 0, -1))
                posts_this_year = BlogArchiveEntry(self._page, year, timestamp)
                self._yearly.append(posts_this_year)
                yearly_index[year] = posts_this_year

            posts_this_year._data_source.append(post)
        self._yearly = sorted(self._yearly,
                key=lambda e: e.timestamp,
                reverse=True)
        self._onIteration()
        return self._yearly

    def _buildMonthlyArchive(self):
        if self._monthly is not None:
            return self._monthly

        self._monthly = []
        for post in self._source.getPages():
            month = post.datetime.strftime('%B %Y')

            posts_this_month = next(
                    filter(lambda m: m.name == month, self._monthly),
                    None)
            if posts_this_month is None:
                timestamp = time.mktime(
                        (post.datetime.year, post.datetime.month, 1,
                            0, 0, 0, 0, 0, -1))
                posts_this_month = BlogArchiveEntry(self._page, month, timestamp)
                self._monthly.append(posts_this_month)

            posts_this_month._data_source.append(post)
        self._monthly = sorted(self._monthly,
                key=lambda e: e.timestamp,
                reverse=True)
        self._onIteration()
        return self._monthly

    def _buildTaxonomy(self, tax_name):
        if tax_name in self._taxonomies:
            return self._taxonomies[tax_name]

        tax_cfg = self._page.app.config.get('site/taxonomies/' + tax_name)
        tax = Taxonomy(tax_name, tax_cfg)

        posts_by_tax_value = {}
        for post in self._source.getPages():
            tax_values = post.config.get(tax.setting_name)
            if tax_values is None:
                continue
            if not isinstance(tax_values, list):
                tax_values = [tax_values]
            for val in tax_values:
                posts = posts_by_tax_value.setdefault(val, [])
                posts.append(post)

        entries = []
        for value, ds in posts_by_tax_value.items():
            source = ArraySource(self._page.app, ds)
            entries.append(BlogTaxonomyEntry(self._page, source, value))
        self._taxonomies[tax_name] = sorted(entries, key=lambda k: k.name)

        self._onIteration()
        return self._taxonomies[tax_name]

    def _onIteration(self):
        if not self._ctx_set:
            eis = self._page.app.env.exec_info_stack
            if eis.current_page_info:
                eis.current_page_info.render_ctx.addUsedSource(self._source)
            self._ctx_set = True


class BlogArchiveEntry(object):
    debug_render = ['name', 'timestamp', 'posts']
    debug_render_invoke = ['name', 'timestamp', 'posts']

    def __init__(self, page, name, timestamp):
        self.name = name
        self.timestamp = timestamp
        self._page = page
        self._data_source = []
        self._iterator = None

    def __str__(self):
        return self.name

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
        source = ArraySource(self._page.app, self._data_source)
        self._iterator = PageIterator(source, current_page=self._page)


class BlogTaxonomyEntry(object):
    debug_render = ['name', 'post_count', 'posts']
    debug_render_invoke = ['name', 'post_count', 'posts']

    def __init__(self, page, source, property_value):
        self._page = page
        self._source = source
        self._property_value = property_value
        self._iterator = None

    def __str__(self):
        return self._property_value

    @property
    def name(self):
        return self._property_value

    @property
    def posts(self):
        self._load()
        self._iterator.reset()
        return self._iterator

    @property
    def post_count(self):
        return self._source.page_count

    def _load(self):
        if self._iterator is not None:
            return

        self._iterator = PageIterator(self._source, current_page=self._page)

