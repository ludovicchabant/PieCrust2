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
        taxonomy_pages:
          categories: pages:_category.%ext%;theme_pages:_category.%ext%
          tags: pages:_tag.%ext%;theme_pages:_tag.%ext%
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
* Taxonomy index pages are defined for `categories` and `tags`. They're set to
  `_category.*` and `_tag.*` respectively, where the extension can be any of the
  auto-formats (which means `.md` and `.textile` by default). They can also fall
  back to the same pages defined in the current theme (whose source name is
  `theme_pages`), which is what makes the default (built-in) PieCrust theme
  work.


## Taxonomies

The default content model defines 2 taxonomies: categories and tags. Categories
are meant to be exclusive, _i.e._ a blog post can only have one category. Tags
are meant to be used more freely, where a blog post can be tagged with multiple
terms.

This shows up more or less like this in the website configuration:

    taxonomies:
      categories:
        term: category
      tags:
        multiple: true
        term: tag


## Routes

The default content model defines routes for the site's pages and blog posts
roughly like such:

    - url: /%path:slug%
      source: pages
      func: pcurl(slug)
    - url: /%year%/%month%/%day%/%slug%
      source: posts
      func: pcposturl(year,month,day,slug)
    - url: /tag/%tag%
      source: posts
      func: pctagurl(tag)
      taxonomy: tags
    - url: /category/%category%
      source: posts
      func: pccaturl(category)
      taxonomy: categories
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
* There are then 2 routes for the taxonomies defined in the default content
  model (tags and categories).
* All routes define some URL functions for use in your pages and templates
  (`pcurl` for pages, `pcposturl` for posts, etc.).
* The last route is meant to match any page defined in the theme. It happens
  last so that a page with the same relative path in your website will properly
  override it.

