---
title: "Appendix 5: Data Providers Reference"
short_title: Data Providers Reference
---

Data providers expose [templating data][tpldata] to the [template
engine][tpleng]. They are used, among other places, by the [sources][src].


## Iterator provider

The iterator provider just provides a list of pages for a given source. This is
the simplest provider.

* `type`: Must be `iterator`.


## Blog provider

This provider gives some structured access to blog data.

* `type`: Must be `blog`.

The templating data exposed by this provider includes:

* `posts`: The list of posts in the given source.
* `years`: A list of years containing blog posts.
* `months`: A list of months containing blog posts.
* `<taxonomy name>`: For any existing taxonomy, lists the terms in use and, for
  each of those, the posts classified with it.

Each `years` and `months` entry contains:

* `name`: The name of the year or month.
* `timestamp`: The timestamp for the year or month.
* `posts`: The list of posts in the year or month.

Each taxonomy term entry contains:

* `name`: The name of the term.
* `posts`: The list of posts classified with the term.
* `post_count`: The number of posts classified with the term. It's useful for
  making things like tag clouds.


[tpldata]: {{docurl('reference/templating-data')}}
[tpleng]: {{docurl('content/templating')}}
[src]: {{docurl('content-model/sources')}}

