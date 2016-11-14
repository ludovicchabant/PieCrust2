---
title: Templating
---

As explained in the documentation about [how PieCrust works][how], the page
contents that you write go through a _templating_ phase, which is when a page
can execute some logic, insert reusable bits of markup, or reference other
pieces of content or metadata from elsewhere in you website.

PieCrust uses [Jinja][] for templating. There's too much data exposed to it to
go over on this page, but check out the [templating data reference][dataref] for
an exhaustive list. The main pieces of data are:

* `page`: the page's configuration header. So if the page has a `title`,
  `page.title` would be its value.

* `pagination`: a pagination object that lets you iterate over other pages
  (typically blog posts). `pagination.items` returns the pages, which come with
  their own metadata (_i.e._ their configuration header) and contents. There are
  also various properties to access counts, next/previous pages, etc.

* `assets`: the current page's [assets][].

* `family`: access to other pages in the same source -- children pages (_i.e._
  pages in a directory of the same name as the current page), sibling pages,
  parent pages, etc.

You can use those pieces of data, and many more, along with Jinja's powerful
template syntax, to make pretty much anything you can think of.


### Debug info window

A very powerful thing to use when using templating data is the PieCrust debug
info window. You can enable it by adding the following to your layouts, just
before the `</body>` tag:

    {%raw%}
    {{ piecrust.debug_info|safe }}
    {%endraw%}

Most of the time, this won't render anything. If, however, you add `?!debug` at
the end of the URL while previewing your website with `chef serve`, then it will
render as small overlay at the bottom right of your browser's window:

![debug info closed]({{assets.debug_info_closed}})

You can then expand the bottom part and reveal all the available templating data
for the current page:

![debug info open]({{assets.debug_info_open}})




[how]: {{docurl('general/how-it-works')}}
[pageconf]: {{docurl('content/page-configuration')}}
[siteconf]: {{docurl('general/website-configuration')}}
[dataref]: {{docurl('reference/templating-data')}}
[assets]: {{docurl('content/assets')}}
[jinja]: http://jinja.pocoo.org/docs/dev/templates/

