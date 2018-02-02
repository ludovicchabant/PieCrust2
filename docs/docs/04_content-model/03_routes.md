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
    You need to use _placeholders_ here (things of the form `%blah%`) otherwise
    all your pages would have the same URL and would be overwriting each other.
  
    The available placeholders depend on the source tied to this route (see
    below). Refer to the [list of available sources][refsrc] to see what kind of
    routing information they expose.

    You'll notice that some routing parameters are *required*, while others are
    *optional*. The *required* parameters *must* be used in the URL pattern. The
    *optional* ones are, well, optional.

  * `source`: This defines the source that this route is defined for. Only pages
    originating from the source of that name will have their bake output
    generated with this route.

Optional settings include:

  * `page_suffix`: Pages that create _sub-pages_ (_e.g._ when using pagination)
    will append this suffix to the route. By default, this is `/%num%`. You _must_
    use the `%num%` placeholder somewhere in this setting.

  * `func`: The name for a *route function* that you can use through the
    [template engine][tpl]. This is what lets you get a URL when you write
    {%raw%}`{{pcurl('foo/bar')}}`{%endraw%} (the function name being `pcurl`
    here) to generate an URL to the `foo/bar.html` page (or something similar).
    The name is up to you, but when you use it, you'll have to pass parameters
    in the same order as they appear in the URL pattern.
    
    So for instance, if you define a route as `/blog/%year%/%slug%`, and that
    route has a `func` name of `post_url`, then you would use it as such:
    `post_url(2016, "some-blog-post")`.

    To know what routing parameters a given source supports, see the reference
    documentation for [sources][refsrc].


## Route ordering

The order of the routes is important, because the first matching route for a
given page will be the one that's used. This is especially important when
running `chef serve`, or running PieCrust as a dynamic CMS.

This is because the incoming URL requested by a visitor's browser will be
matched against each route starting from the first one in the list. For each
route that matches, an actual page will be looked for, and the first one to be
found will be returned for that URL.



[tpl]: {{docurl('content/templating')}}
[refsrc]: {{docurl('reference/sources')}}
[refgen]: {{docurl('reference/generators')}}

