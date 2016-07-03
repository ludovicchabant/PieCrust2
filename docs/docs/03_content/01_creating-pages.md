---
title: Creating Pages
---

In PieCrust, creating pages is a matter of creating a text file in the correct
place with the correct name. This mostly depends on the [page sources][src]
you're using, but we can go over how it works for the sources involved in the
[default content model][dcm].

We will also mention the `chef prepare` command, which semi-automates the
process of creating pages by letting you type a lot less than what would be
otherwise needed to create the correctly named text file in the correct folder.
Generally speaking, you should be able to run `chef prepare -h` and figure it
out on your own.

> In addition to creating the text file, you can make PieCrust open your
> favorite text editor too, with the `prepare/editor` site configuration
> setting. For more information, see the [site configuration
> reference][confref].


## Overview

All pages sources have a _file-system endpoint_, which is usually a
sub-directory of your website's root directory. They will look for pages inside
that endpoint, and load any file that matches that source's naming convention.

Generally speaking, page sources will load any files that:

* have a `.html` extension.
* have an extension listed in the `site/auto_formats` website setting (by
  default, those are `.md` and `.textile`, for Markdown and Textile formatted
  pages respectively).

Different sources have different conventions -- mostly naming of the page files.
We'll look at how it works for the sources in the [default content model][dcm].
To learn about other sources, see the [page sources reference][srcref].


## Default content model pages

### Simple pages

When using the default content model, PieCrust will load simple pages out of the
`pages/` endpoint. The relative path of a page from the `pages/` directory will
be that page's _slug_, _i.e._ its URL, minus the site's root, and minus any
optional arguments.

Since there are often no arguments, and the default's site root is `/`, it's
pretty much the same as the page's URL. So a page located at
`pages/cooks/ludovic` will have an URL of `/cooks/ludovic`.

> Running `chef prepare page cooks/ludovic` will create that page for you, which
> means you don't have to bother with creating intermediate sub-directories or
> whatnot.


### Blog posts

When using the default content model, PieCrust will load blog posts out of the
`posts/` endpoint. There are different naming conventions available depending on
the `site/posts_fs` setting:

* `flat`: `YYYY-MM-DD_post-slug.ext`
* `shallow`: `YYYY/MM-DD_post-slug.ext`
* `hierarchy`: `YYYY/MM/DD_post-slug.ext`

Where:

* `YYYY`, `MM`, and `DD` are the year, month, and day of the post,
respectively.
* `post-slug` is, well, the post's slug (_i.e._ the part of the URL that comes
  after the site's root).
* `ext` is an extension that's either `html`, or something in the site's
  auto-formats (usually `md` for Markdown texts and `textile` for Textile
  texts).

> Running `chef prepare post my-new-blog-post` will create a new blog post with
> a slug of `my-new-blog-post`, dated today. This makes it quick to write a new
> blog post!


[src]: {{docurl('content-model/sources')}}
[dcm]: {{docurl('content-model/default-model')}}
[srcref]: {{docurl('reference/sources')}}
[confref]: {{docurl('reference/website-configuration')}}

