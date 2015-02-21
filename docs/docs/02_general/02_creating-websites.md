---
title: Creating Websites
---

A PieCrust website is really just a directory with a special structure.

For a default website configuration, it will look a bit like this:

    <root>
      |---- assets/
      |       |--- css/
      |       |--- img/
      |       +--- js/
      |---- pages
      |       |--- about.md
      |       |--- blog.md
      |       +--- projects/
      |               |--- bar.md
      |               +--- foo.md
      |---- posts
      |       |--- 2014-10-23_new-foo-project.md
      |       +--- 2014-10-29_some-stuff-about-something.md
      |---- templates
      |       |--- default.html
      |       |--- blog.html
      |       +--- post.html
      +---- config.yml



## The config file

The main thing that differentiates any directory from a PieCrust website is the
`config.yml` file that's in it. That's what `chef` looks for in order to know
where your site root is -- and it will look in parent directories too, which
means it will work also if you're in a sub-directory of your website.

If no `config.yml` file is found, `chef` will return and print an error about
it.

For more information on the configuration file, see [Website Configuration][1]
and the related [reference][2].

[1]: {{docurl('general/website-configuration')}}
[2]: {{docurl('reference/website-configuration')}}


## Special directories

A PieCrust website has a couple of special directories that you probably don't
want to mess around with (unless you know what you're doing).

* `_cache`: this directory contains cached information and intermediate files
  that allow PieCrust to run faster. The `chef purge` command will delete it,
  which can be necessary if it has been corrupted, or if you want to start
  fresh.

* `_counter`: this is the default output directory for a bake (`chef bake`
  command). That's where the static version of your site would be generated, for
  you to upload to your public server. Like the `_cache` directory, you can also
  safely delete `_counter`, and PieCrust will just generate it again. And of
  course, you can always pass a different output directory to `chef bake` so
  that you never see `_counter`.


## Content directories

PieCrust will only look for content (mostly pages) in directories that you point
it to.

All of this is configurable, of course, but by default, these are:

* `pages`: that's where PieCrust will look for all your pages. Any file in there
  with a `.html`, `.md`, or `.text` extension (among others) will be turned into
  a page.

* `posts`: just like `pages`, PieCrust will look for all your posts in this
  directory, but it will expect filenames to be formatted a certain way --
  namely, `YYYY-MM-DD_title-of-post`. In PieCrust terms, those 2 directories are
  not really different, as they're both "page sources" with different source
  types. For more information on this, see [Content Model][3].

* `templates`: Where pages and posts define the _contents_ of said pages and
  posts, files found in the `templates` directory define the layouts and other
  re-usable bits of markup that are used by those pages and posts.

All those directories are configurable through the [website configuration][1].
This means that if, instead of "_pages_" and "_posts_" (which is a content model
suitable for a blog) you wanted "_products_", "_updates_", and "_pages_" (which would be
suitable for a company's website), you can totally do that.


## Asset directories

PieCrust will look for assets in the aptly named `assets` directory.

This should contain your images, CSS files, Javascript files, `robots.txt`,
`favicon.ico`, etc.  PieCrust comes with a very capable built-in asset pipeline,
and, in most cases, putting that stuff in there will "just work".

However, if you have advanced requirements for how you want your assets to be
processed, or if you just prefer using another asset pipeline (like Grunt or
Gulp), there are also simple ways to not have any `assets` directory, so that
PieCrust effectively only takes care of your actual content. Again, see the
[website configuration][1] page.


## Miscellaneous

Any other directory or file will be ignored by PieCrust. If you customized
your website configuration on that front, anything not specifically mentioned in
it will be ignored.

This means that directories like `bower_components` or `node_modues` are free to
co-exist with PieCrust.


[3]: {{docurl('content-model')}}

