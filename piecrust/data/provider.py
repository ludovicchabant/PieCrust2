import time
from piecrust.data.iterators import PageIterator
from piecrust.sources.array import ArraySource


class DataProvider(object):
    debug_render_dynamic = ['_debugRenderUserData']
    debug_render_invoke_dynamic = ['_debugRenderUserData']

    def __init__(self, source, page, user_data):
        if source.app is not page.app:
            raise Exception("The given source and page don't belong to "
                            "the same application.")
        self._source = source
        self._page = page
        self._user_data = user_data

    def __getattr__(self, name):
        if self._user_data is not None:
            try:
                return self._user_data[name]
            except KeyError:
                pass
        raise AttributeError()

    def __getitem__(self, name):
        if self._user_data is not None:
            return self._user_data[name]
        raise KeyError()

    def _debugRenderUserData(self):
        if self._user_data:
            return list(self._user_data.keys())
        return []


class IteratorDataProvider(DataProvider):
    PROVIDER_NAME = 'iterator'

    debug_render_doc = """Provides a list of pages."""

    def __init__(self, source, page, user_data):
        self._innerIt = None
        if isinstance(user_data, IteratorDataProvider):
            # Iterator providers can be chained, like for instance with
            # `site.pages` listing both the theme pages and the user site's
            # pages.
            self._innerIt = user_data
            user_data = None

        super(IteratorDataProvider, self).__init__(source, page, user_data)
        self._pages = PageIterator(source, current_page=page)
        self._pages._iter_event += self._onIteration
        self._ctx_set = False

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, key):
        return self._pages[key]

    def __iter__(self):
        yield from iter(self._pages)
        if self._innerIt:
            yield from self._innerIt

    def _onIteration(self):
        if not self._ctx_set:
            eis = self._page.app.env.exec_info_stack
            eis.current_page_info.render_ctx.addUsedSource(self._source.name)
            self._ctx_set = True


class BlogDataProvider(DataProvider):
    PROVIDER_NAME = 'blog'

    debug_render_doc = """Provides a list of blog posts and yearly/monthly
                          archives."""
    debug_render = ['posts', 'years', 'months']
    debug_render_dynamic = (['_debugRenderTaxonomies'] +
            DataProvider.debug_render_dynamic)

    def __init__(self, source, page, user_data):
        super(BlogDataProvider, self).__init__(source, page, user_data)
        self._yearly = None
        self._monthly = None
        self._taxonomies = {}
        self._ctx_set = False

    def __getattr__(self, name):
        if self._source.app.getTaxonomy(name) is not None:
            return self._buildTaxonomy(name)
        return super(BlogDataProvider, self).__getattr__(name)

    @property
    def posts(self):
        it = PageIterator(self._source, current_page=self._page)
        it._iter_event += self._onIteration
        return it

    @property
    def years(self):
        return self._buildYearlyArchive()

    @property
    def months(self):
        return self._buildMonthlyArchive()

    def _debugRenderTaxonomies(self):
        return [t.name for t in self._source.app.taxonomies]

    def _buildYearlyArchive(self):
        if self._yearly is not None:
            return self._yearly

        self._yearly = []
        for post in self._source.getPages():
            year = post.datetime.strftime('%Y')

            posts_this_year = next(
                    filter(lambda y: y.name == year, self._yearly),
                    None)
            if posts_this_year is None:
                timestamp = time.mktime(
                        (post.datetime.year, 1, 1, 0, 0, 0, 0, 0, -1))
                posts_this_year = BlogArchiveEntry(self._page, year, timestamp)
                self._yearly.append(posts_this_year)

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

        tax_info = self._page.app.getTaxonomy(tax_name)
        setting_name = tax_info.setting_name

        posts_by_tax_value = {}
        for post in self._source.getPages():
            tax_values = post.config.get(setting_name)
            if tax_values is None:
                continue
            if not isinstance(tax_values, list):
                tax_values = [tax_values]
            for val in tax_values:
                posts_by_tax_value.setdefault(val, [])
                posts_by_tax_value[val].append(post)

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
            eis.current_page_info.render_ctx.addUsedSource(self._source)
            self._ctx_set = True


class BlogArchiveEntry(object):
    def __init__(self, page, name, timestamp):
        self.name = name
        self.timestamp = timestamp
        self._page = page
        self._data_source = []
        self._iterator = None

    def __str__(self):
        return self.name

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

        self._iterator = PageIterator(self._source, self._page)

