---
title: Content Model
---

PieCrust is a CMS, _i.e._ a _Content Management System_. It looks, by default,
like a simple blog engine, but it can really handle any arbitrary set of
content. You need however to define what that content is. This is the _content
model_.

The [default content model][def] is what you get out of the box. It defines a
simple blog site where you can have pages and posts.

To create more complex or customized websites, you can define another content
model by specifying [sources][], [routes][], and [generators][] in the [site
configuration][siteconf]:

* [Sources][] are how you tell PieCrust where to find your content. It defines
  what sub-directories contain what kind of pages, with what kind of naming
  convention, and what kind of metadata. In theory, sources can also provide
  pages from other places than the file-system -- like a network connection or
  a ZIP file or a database or whatever.

* [Routes][] define how the content returned by the sources is exposed to your
  visitors. This defines both the URLs for that content, and the place on disk
  where it will be baked to.

* [Generators][] define special types of sources which can procedurally generate
  pages based on other content. A common type of generator is a "taxonomy"
  generator, for things like "tags" or "categories". Based on how you've tagged
  your blog posts, a generator would generate one page for each unique tag.


[def]: {{docurl('content-model/default-model')}}
[sources]: {{docurl('content-model/sources')}}
[routes]: {{docurl('content-model/routes')}}
[generators]: {{docurl('content-model/generators')}}
[siteconf]: {{docurl('general/website-configuration')}}

