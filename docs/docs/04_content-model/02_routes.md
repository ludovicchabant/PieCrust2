---
title: Routes
---

_Routes_ define how your content is exposed to your visitors. This affects the
structure of your baked output, which affects the URLs of your pages.

Routes are defined as a list of entries under `site/routes`:

    site:
        routes:
            - url: /foo/%slug%
              source: something
            - url: /bar/%year%/%month%/%slug%
              source: otherthing

Each route must define the following settings:

* `url`: That's the pattern to use to figure out where the baked page will go.
  You obviously need to use _placeholders_ here (things of the form `%blah%`)
  otherwise all your pages would be overwriting each other -- although PieCrust
  would warn you about that. The available placeholders depend on the source
  tied to this route. See the [list of available sources][refsrc] to see what
  kind of routing information they expose.

* `source`: This defines the source that this route is defined for. Only pages
  coming from that source will have their bake output generated from this route.

Optional settings include:

* `taxonomy`: If this route is meant to match a taxonomy index page, you have to
  define which taxonomy that is.

* `page_suffix`: Pages that create _sub-pages_ (_e.g._ when using pagination)
  will append this suffix to the route. By default, this is `/%num%`. You _must_
  use the `%num%` placeholder somewhere in this setting.


## Route ordering

The order of the routes is important, because the first matching route for a
given page will be the one that's used. This is especially important when
running `chef serve`, or running PieCrust as a dynamic CMS.

This is because the incoming URL requested by a visitor's browser will be
matched against each route starting from the first one in the list. For each
route that matches, an actual page will be looked for, and the first one to be
found will be returned for that URL.



[refsrc]: {{docurl('reference/sources')}}

