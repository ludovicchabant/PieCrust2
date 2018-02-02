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

The default sources define what you would expect for a personal website:
"free-form" pages (`pages`), blog posts (`posts`), taxonomies (`tags` and
`categories`), and yearly archives.


### Pages

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


### Blog posts

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


### Taxonomies

The default content model defines 2 taxonomies: "categories" and "tags".
Categories are meant to be exclusive, _i.e._ a blog post can only have one
category. Tags are meant to be used more freely, where a blog post can be tagged
with multiple terms.

This shows up more or less like this in the website configuration:

    site:
      taxonomies:
        categories:
          term: category
          func_name: pccaturl
        tags:
          multiple: true
          term: tag

PieCrust then creates a `taxonomy` source for each defined taxonomy (including
custom taxonomies you added or changed in `sites/taxonomies`). Each taxonomy
source will look like this:

    site:
      sources:
        posts_TAXONOMY:
          type: taxonomy
          taxonomy: TAXONOMY
          source: posts
          template: _TERM.html

In this example, `TAXONOMY` is the name of the taxonomy (_e.g._: `tags`), and
`TERM` is the `term` value (_e.g._: `tag`). If no `term` is defined, the name of
the taxonomy is used.

As you can see, the taxonomy index layout templates are set to `_category.html`
and `_tag.html` respectively.


### Archives

The blog archives source is defined like this by default:

    site:
      sources:
        posts_archives:
          type: blog_archives
          source: posts
          template: _year.html

The index layout template for each year of archives is set to `_year.html`.


## Routes

The default content model defines routes for the site's pages and blog posts
roughly like such:

    - url: /%path:slug%
      source: pages
      func: pcurl

    - url: /%year%/%month%/%day%/%slug%
      source: posts
      func: pcposturl

    - url: /archives/%year%
      source: posts_archives
      func: pcyearurl

    - url: /tag/%tag%
      source: posts_tags
      func: pctagurl

    - url: /category/%category%
      source: posts_categories
      func: pccaturl

    - url: /%path:slug%
      source: theme_pages
      func: pcurl

Let's go through it:

* The `pages` source is exposed in the most simple way: just a single route,
  rooted to `/`. Whatever `slug` gets returned for a page (which is pretty much
  the relative path of the page's file) will be its URL.

* Blog posts (from the `posts` source) are exposed with a `/year/month/day/slug`
  URL, which matches the type of routing metadata the `posts/*` sources offer.
  If the `post_url` is set, the route will be changed accordingly. If there's
  more than one blog in `site/blogs`, there will be more than one route for
  posts, and the route will be rooted with `/<blogname>`.

* The next route is for the blog archives source.

* There are then routes for the taxonomy sources. By default, there are
  2 taxonomies (tags and categories) so that's 2 routes.

* All routes define some URL functions for use in your pages and templates
  (`pcurl` for pages, `pcposturl` for posts, etc.). Note that by default the
  `categories` taxonomy would have a `pccategoryurl` route function, which is
  a bit too long to type, so by default that taxonomy specifies a `func_name` to
  override that to `pccaturl`.

* The last route is meant to match any page defined in the theme. It happens
  last so that a page with the same relative path in your website will properly
  override it.

