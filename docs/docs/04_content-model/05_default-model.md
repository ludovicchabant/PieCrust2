---
title: Default Content Model
---

The default content model that you get with PieCrust out of the box is a generic
"blog engine" model. It can be configured, to a degree, using some simple
website configuration settings that operate at a higher level about the content
model.

Understanding how this all work can be useful to understand how the PieCrust
content model can be tweaked to one's liking.

## Sources

The default sources define the strict minimum for a personal website:
"free-form" pages (`pages`) and blog posts (`posts`).

First, the pages:

    sources:
      pages:
        data_endpoint: site.pages
        item_name: page

Here's a breakdown of those settings:

* The `pages` source is anchored at the default location, which is a
  sub-directory with the same name as the source (`/pages`).
* It's using the default source backend (named `default`) which just returns any
  file inside its sub-directory as a page.
* It exposes all those pages as a simple iterator (the default) at `site.pages`.
* It defines the `item_name` so that you can prepare a new page with `chef
  prepare page`.

The `posts` sources is a bit more complicated:

    sources:
      posts:
        type: posts/flat
        fs_endpoint: posts
        data_endpoint: blog
        data_type: blog
        default_layout: post
        item_name: post

Here's what this does:

* The `posts` source is also anchored at the default location (`/posts`). But if
  the `site/blogs` setting lists more blogs, each blog will be listed under
  `/posts/<blogname>`, effectively changing the `fs_endpoint` setting.
* It's using the `posts/flat` backend, which means blog posts should be named
  with the date at the beginning of the filename. The `site/posts_fs` changes
  this to `posts/<fsname>`.
* All blog posts are exposed through the `blog` data endpoint, with a `blog`
  data provider -- which means you can also access blog archives in addition to
  a flat list of all blog posts. If the `site/blogs` setting lists more blogs,
  each blog will have its `data_endpoint` set to its name.
* The default layout to use for all blog posts is set to `post` instead of
  `default`.


## Generators

### Taxonomies

The default content model defines 2 taxonomies: categories and tags. Categories
are meant to be exclusive, _i.e._ a blog post can only have one category. Tags
are meant to be used more freely, where a blog post can be tagged with multiple
terms.

This shows up more or less like this in the website configuration:

    site:
      taxonomies:
        categories:
          term: category
          func_name: pccaturl
        tags:
          multiple: true
          term: tag

PieCrust then creates a `taxonomy` generator for each defined taxonomy
(including custom taxonomies you added). Each taxonomy generator will look like
this:

    site:
      generators:
        posts_FOOS:
          type: taxonomy
          taxonomy: FOOS
          source: posts
          page: "pages:_FOO.%ext%;theme_pages:_FOO.%ext%"

In this example, `FOOS` is the name of the taxonomy (_e.g._: `tags`), and `FOO`
is the `term` value (_e.g._: `tag`). If no `term` is defined, the name of the
taxonomy is used.

As you can see, the taxonomy index pages are set to `_category.*` and `_tag.*`
respectively, where the extension can be any of the auto-formats (which means
`.md`, `.textile`, and `.html` by default). They can also fall back to the same
pages defined in the current theme (whose source name is `theme_pages`), which
is what makes the default (built-in) PieCrust theme work, for instance.

### Archives

The blog archives generator is defined like this by default:

    site:
      generators:
        posts_archives:
          type: blog_archives
          source: posts
          page: "pages:_year.%ext%;theme_pages:_year.%ext%"

The index page for each year of archives is set to `_year.*`, where the
extension can be any of the auto-formats (which means `.md`, `.textile`, and
`.html` by default). It can also fall back to the same page defined in the
current theme (whose source name is `theme_pages`), which is what makes the
default (built-in) PieCrust theme work, for instance.


## Routes

The default content model defines routes for the site's pages and blog posts
roughly like such:

    - url: /%path:slug%
      source: pages
      func: pcurl(slug)

    - url: /%year%/%month%/%day%/%slug%
      source: posts
      func: pcposturl(year,month,day,slug)

    - url: /archives/%year%
      generator: posts_archives
      func: pcyearurl(year)

    - url: /tag/%tag%
      generator: posts_tags
      func: pctagurl(tag)

    - url: /category/%category%
      generator: posts_categories
      func: pccaturl(category)

    - url: /%path:slug%
      source: theme_pages
      func: pcurl(slug)

Let's go through it:

* The `pages` source is exposed in the most simple way: just a single route,
  rooted to `/`. Whatever `slug` gets returned for a page (which is pretty much
  the relative path of the page's file) will be its URL.

* Blog posts (from the `posts` source) are exposed with a `/year/month/day/slug`
  URL, which matches the type of routing metadata the `posts/*` sources offer.
  If the `post_url` is set, the route will be changed accordingly. If there's
  more than one blog in `site/blogs`, there will be more than one route for
  posts, and the route will be rooted with `/<blogname>`.

* The next route is for the blog archives generator.

* There are then routes for the taxonomy generators. By default, there are
  2 taxonomies (tags and categories) so that's 2 routes.

* All routes define some URL functions for use in your pages and templates
  (`pcurl` for pages, `pcposturl` for posts, etc.). Note that by default the
  `categories` taxonomy would have a `pccategoryurl` route function, which is
  a bit too long to type, so by default that taxonomy specifies a `func_name` to
  override that to `pccaturl`.

* The last route is meant to match any page defined in the theme. It happens
  last so that a page with the same relative path in your website will properly
  override it.

