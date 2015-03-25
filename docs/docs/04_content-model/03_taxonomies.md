---
title: Taxonomies
---

Taxonomies in PieCrust define pieces of page metadata for which you want to have
_index pages_ created for you.

## Taxonomy example

A common example of taxonomies is the "_category_" of a blog post. If you have
blog posts in categories "_recipes_", "_kitchen tips_" and "_restaurant
reviews_", you want 3 pages to be created automatically for you so that someone
can see a list of all recipes, kitchen tips, and restaurant reviews (and those
pages may have _sub-pages_ if they're using pagination to only show 10 or so at
a time).

But if you write a new blog post and put it in category "_utensil reviews_", you
want a new page listing all utensil reviews to also be created.

You basically want PieCrust to "dynamically" generate those listing pages
(called "_taxonomy index pages_") for each _value_ ever used in that given
taxonomy.


## Taxonomy configuration

Taxonomies are defined under `site/taxonomies` in the website configuration:

    site:
        taxonomies:
            categories:
                multiple: true
                page: pages:_cat.md
            authors:
                page: pages:_author.md

These settings should be defined as a map. Each entry is the name of the
taxonomy, and is associated with the settings for that taxonomy. Settings
include:

* `multiple`: Defines whether a page can have more than one value assigned for
  this taxonomy. Defaults to `false` (_i.e._ only a single value can be
  assigned).

* `term`: Taxonomies are usually named using plural nouns. The `term` setting
  lets you define the singular form, which is used to make some messages read
  better.

* `page`: Defines the page to use to generate the _index page_ for this
  taxonomy. This is a [page reference][pageref].


[pageref]: {{docurl('content-model/page-references')}}

