---
title: "Appendix 4: Generators Reference"
short_title: Generators Reference
---

Here are the generators that come with PieCrust by default.


## Taxonomy generator

A taxonomy is a way to classify content. The most common taxonomies are things
like "_tags_" or "_categories_" that you use to classify blog posts.

The taxonomy generator creates _index pages_ that list all the content in every
_taxonomy term_ in use. 

### Taxonomy example

A common example of taxonomies is the "_category_" of a blog post. If you have
blog posts in categories "_recipes_", "_kitchen tips_" and "_restaurant
reviews_", you want 3 pages to be created automatically for you so that someone
can see a list of all recipes, kitchen tips, and restaurant reviews. Those
3 pages may of course have _sub-pages_ if they're using pagination to only show
10 or so at a time.

If you write a new blog post and put it in category "_utensil reviews_", you
want a new page listing all utensil reviews to also be created.

### Generator configuration

The taxonomy generator takes the following configuration settings:

* `type`: Needs to be `taxonomy`.

* `taxonomy`: The name of a taxonomy, defined under `site/taxonomies`. See below
  for more information.

* `source`: The name of a source from which to look for classified content. For
  example, `posts` is the name of the default blog posts source.

* `page`: A [page reference][pageref] to an index page to use for each generated
  page. This index page will be passed some template data to list the
  appropriate content (more on this later).

### Taxonomy configuration

Taxonomies are defined under `site/taxonomies` in the website configuration:

    site:
        taxonomies:
            tags:
                multiple: true
                term: tag

These settings should be defined as a map. Each entry is the name of the
taxonomy, and is associated with the settings for that taxonomy. Settings
include:

* `multiple`: Defines whether a page can have more than one value assigned for
  this taxonomy. Defaults to `false` (_i.e._ only a single value can be
  assigned).

* `term`: Taxonomies are usually named using plural nouns. The `term` setting
  lets you define the singular form, which is used in multiple places.

### Template data

When the taxonomy generator renders your _index page_, it will pass it the
following template data:

* `<taxonomy_name>` (the taxonomy name) will contain the term, or terms, for the
  current listing. For instance, for a "_tags_" taxonomy, it will contain the
  list of tags for the current listing. In 99% of cases, that list will contain
  only one term, but for "_term combinations_" (i.e. listing pages tagged with
  2 or more tags), it could contain more than one. For taxonomies that don't
  have the `multiple` flag, though, that template data will only be a single
  term (_i.e._ a string value).

* `pagination.items` will list the classified content, _i.e._ content from the
  generator's `source`, filtered for only content with the current term. For
  instance, the list of blog posts with the current tag or category or whatever.
  Note that this is still pagination data, so it will create _sub-pages_.


## Blog archives

This generator will generate one page per year for a given source of pages. This
is useful for generating yearly blog archives.

### Generator configuration

The blog archives generator takes the following configuration settings:

* `type`: Needs to be `blog_archives`.

* `source`: The name of a source from which to look for dated content.

* `page`: A [page reference][pageref] to an index page to use for each generated
  yearly archive page.

### Template data

When the blog archives generator renders your _index page_, it will pass it the
following template data:

* `year` is the current year.

* `pagination.items` lists the content dated for the current year, in
  reverse-chronological order. This will potentially create _sub-pages_ since
  this is pagination data.

* `archives` lists the same thing as `pagination.items`, but without paginating
  anyting, _i.e._ even if you have _lots_ of blog posts in a given year, they
  will all be listed on the same page, instead of being listed, say, 10 per
  page, with _sub-pages_ created for the rest. Also, `archives` will list posts
  in chronological order.


[pageref]: {{docurl('content-model/page-references')}}

