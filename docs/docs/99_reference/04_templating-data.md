---
title: "Appendix 4: Templating Data Reference"
short_title: Templating Data Reference
---

When a page or layout gets rendered, it goes through a templating phase. During
that phase, PieCrust builds the _template data_ that gets passed to the template
engine.

This page shows a list of all the data that gets created for this occasion. Note
that most of this data is in fact created "on-demand" (_i.e._ lazily evaluated)
so that you only pay the price of whatever you use.

Note that you can inspect this data yourself by using the debug window.


* `piecrust`: Contains data specific to PieCrust itself.

    * `version`: The version number of PieCrust.

    * `url`: URL to the official PieCrust website.

    * `branding`: A short message saying "_Baked with PieCrust_", along with a
      link to the official website.

    * `debug_info`: If enabled, the debug window.

* `page`: Contains the page's metadata. This is basically the page's configuration header, as you wrote it, plus any default values for things you omitted, and any additional values set by sources (like the `ordered` or `autoconfig` sources) or plugins.

  Notable additional data includes:

    * `url`: The URL of the page.
    * `slug`: The slug of the page.
    * `timestamp`: The UNIX timestamp of the page.
    * `date`: The formatted (user-friendly) version of the page's timestamp,
      according to the `site/date_format` setting.

* `assets`: The list of assets for this page.

    * It can be iterated upon, to list all assets.
    * It can be accessed by name, to access a specific asset.

* `pagination`: Gives access to a paginating version of the default source's
  list of pages. The default source will be the first blog in the website, if
  any (as defined by `site/blogs`). It can be overriden by setting the `source`
  or `blog` setting on the current page, in which case a source of that name
  will be used.

  Note that the object returned by `pagination`, called a paginator, can also be
  returned by other things, like the `paginate()` template function, for
  instance. As such, it does not assume that the items it is paginating are
  posts or pages.

    * `has_more`: Whether there are more items.

    * `items` (or `posts`): The list of items.

    * `has_items`: Whether there are any items.

    * `items_per_page`: Returns how many maxiumum items there are for each
      sub-page. Can be overriden locally with the `items_per_page` setting in
      the page configuration.

    * `items_this_page`: Returns the number of actual items on the current
      sub-page. This will always be `items_per_page` except for the last page
      (which can be the first page).
    
    * `prev_page_number`: The previous sub-page number, if any.

    * `this_page_number`: The current sub-page number. The first page is number
      `1`.
    
    * `next_page_number`: The next sub-page number, if any.

    * `prev_page`: The URL to the previous sub-page, if any.

    * `this_page`: The URL to the current sub-page.

    * `next_page`: The URL to the next sub-page, if any.

    * `total_item_count`: The total number of items across all sub-pages.

    * `total_page_count`: The total number of sub-pages.

    * `next_item`: The next item, if any.

    * `prev_item`: The previous item, if any.

    * `all_page_numbers(radius)`: A function that returns a list of page
      numbers. With no argument, this returns a list of all page numbers, from 1
      to the last number. With an argument, this returns a subset of this list,
      with a "radius" equal to the argument "around" the current sub-page.

    * `page(index)`: Returns the URL of a sub-page of the given number.

* `family`: Returns a piece of data that lets you access parents, siblings, and
  children of the current page. This is only possible for page sources that
  support hierarchical navigation (but most of those shipping with PieCrust do).

    * `siblings`: Returns a list of the current page's siblings, _i.e._ pages on
      the same "level" as the current one.

    * `children`: Returns a list of the current page's children, _i.e._ pages
      that are "under" the current page. In most cases, this means pages that
      are in a sub-directory with the same name as the current page's file name.

    * `root`: Returns the root of the current page's source, so that you can
      traverse all pages in a hierarchical manner.

    * `forpath(path)`: Returns the family data starting at the given relative
      path.

* All the website configuration is merged with the data.

* All source data providers are also included. For example, in the default
  content model, the `pages` source is exposed to `site/pages`, so using
  `site.pages` through the template engine would return a complete list of all
  the pages in your website.

