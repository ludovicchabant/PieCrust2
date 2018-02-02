---
title: "Appendix 3: Sources Reference"
short_title: Sources Reference
---

Here are the page sources that come with PieCrust by default.


## Default source

The `default` source makes a page out of any file found in its file-system
endpoint.

* Type: `default`

* Configuration settings:
    * `fs_endpoint`: The directory (relative to the website's root) in which the
      source will find page files. Defaults to the name of the source.

* Metadata provided:
    * `slug`: The "_slug_" of the page, which is in this case the relative path
      of the page file from the file-system endpoint. If the file's extension is
      on of the `site/auto_formats` (`.md`, `.textile`), the extension is
      stripped from the slug.

* Required routing parameter:
    * `slug`


## Auto-configuring source

The `autoconfig` source sets a page configuration setting on every page that it
produces based on the relative path of each page file. This is useful if you
want, for example, pages to be tagged or categorized based on any sub-directory
they're in.

* Type: `autoconfig`

* Configuration settings:
    * `fs_endpoint`: Same as for the `default` source.
    * `setting_name`: Specifies what page configuration setting will be set from
      the page file's path.
    * `capture_mode`: Either `path`, `dirname`, or `filename`. This defines how
      the page file's path should be parsed:
        * `path` means the whole relative path will be parsed.
        * `dirname` means the relative directory will be parsed.
        * `filename` means only the filename will be parsed.
    * `only_single_values`: The source will raise an error if the page is placed
      in more than one sub-directory.
    * `collapse_single_values`: If the page is placed inside a single
      sub-directory, don't set the `setting_name` configuration setting to a
      list with one value in it -- instead, set the configuration setting to
      that value directly.

* Metadata provided:
    * `slug`: Same as for the `default` source.
    * `config`: A page configuration fragment containing the `setting_name` and
      its value extracted from the page's relative path.

* Required routing parameter:
    * `slug`


## Ordered source

This source orders pages and sub-directories according to a numerical prefix.
All sub-directory and file names must start with `XX_`, where `XX` is a number.
The prefix is then stripped from the page slug, along with all prefixes from
parent sub-directories. The end result looks much like a `default` source, but
with the added ability to order things easily using the file-system.

* Type: `ordered`

* Configuration settings:
    * `fs_endpoint`: Same as for the `default` source.
    * `setting_name`: The page configuration setting in which the order value
      will be stored. Defaults to `order`.
    * `default_value`: The value to assign to `setting_name` in case no prefix
      was found on a particular directory or file name. Defaults to `0`.

* Metadata provided:
    * `slug`: Same as for the `default` source. The prefixes with the order
      values are stripped away.
    * `config`: A page configuration fragment containing the `setting_name` and
      its value extracted from the page file's name prefix.

* Required routing parameter:
    * `slug`

* Notes:
    * A setting called `<setting_name>_trail` will also be created in each
      page's metadata, which contains a list of all the order values starting
      from the first sub-directory, all the way to the page's file name.

    * Ordering pages can already be achieved easily with the `default` source,
      by just assigning order values in pages' configuration headers and sorting
      iterators based on that. The advantages over the `ordered` source are that
      it's less strict, allows for multiple sort parameters, and it doesn't
      require renaming files to re-order things.  The disadvantages are that
      it's hard to see the overall order at a glance.


## Blog posts sources

There are 3 blog posts sources offering slightly different file structures:

* `posts/flat`: Files must all be in the same directory, and be named
  `%year%-%month%-%day%_%slug%`.
* `posts/shallow`: Files must be in a sub-directory named after the year. Each
  file must be named `%month%-%day%_%slug%`.
* `posts/hierarchy`: File must be in a sub-directory named after the year, and a
  sub-directory named after the month's number. Each file must be named
  `%day%_%slug%`.

You probably want to choose the correct file structure based on your personal
tastes and blogging frequency. Putting all files in the same folder is a lot
easier to manage, but quickly gets annoying if you post updates once a day or
more, and end up with a thousand files in there after a few years.

* Type: `posts/flat`, `posts/shallow`, or `posts/hierarchy`

* Configuration settings:
    * `fs_endpoint`: The directory, relative to the website root, in which posts
      will be searched for.

* Metadata provided:
    * `year`, `month`, and `day`: The date components extracted from the page
      file's path.
    * `date`: The timestamp extracted from the date components.
    * `slug`: Just like for the `default` source. This here is the part that
      comes after the date prefix.

* Required routing parameters:
    * `slug`

* Optional routing parameters:
    * `year`, `month`, `day`. Works best when those parameters are declared as
      integers (`%int:year%`) or more precisely `int4` (for `year`) and `int2`
      (for `month` and `day`) so you get proper `0` padding.

* Notes:
    * To specify the time of day of a blog post, set the `time` setting in the
      page's configuration header.

    * You can already assign date/times to pages in the `default` source by
      using the configuration header. It however prevents you from seeing all
      your blog posts in order when listing your files, and prevents you from
      being able to have 2 different blog posts sharing the same slug/title.


## Prose source

This source is like a `default` source, but is meant for page with no
configuration header. This is useful if you want to keep your pages completely
clean of any PieCrust-isms of any kind -- just pure Markdown or Textile or
whatever.

* Type: `prose`

* Configuration settings:
    * Same as for the `default` source.
    * `config`: The "page configuration recipe" for pages created by this
      source. Right now, the only "dynamic" aspect you can give this is to set
      the `title` to `%first_line%`, which means the title will be extracted
      from the first non-blank line in the page file.

* Metadata provided:
    * `slug`: Same as for the `default` source.
    * `config`: The page configuration recipe set in the source configuration,
      with any dynamic settings resolved.

* Required routing parameter:
    * `slug`


## Taxonomy source

A taxonomy is a way to classify content. The most common taxonomies are things
like "_tags_" or "_categories_" that you use to classify blog posts.

The taxonomy source creates _index pages_ that list all the content in every
_taxonomy term_ in use.

A common example of taxonomy is the "_category_" of a blog post. If you have
blog posts in categories "_recipes_", "_kitchen tips_" and "_restaurant
reviews_", you want 3 pages to be created automatically for you so that someone
can see a list of all recipes, kitchen tips, and restaurant reviews. Those
3 pages may of course have _sub-pages_ if they're using pagination to only show
10 or so at a time.

If you write a new blog post and put it in category "_utensil reviews_", you
want a new page listing all utensil reviews to also be created.

The taxonomy source creates those pages (one for each category) dynamically for
you.

* Type: `taxonomy`

* Configuration settings:
  * `taxonomy`: The name of a taxonomy, defined under `site/taxonomies`. See below
    for more information.
  * `source`: The name of a source from which to look for classified content. For
    example, `posts` is the name of the default blog posts source.
  * `template`: The name of a layout template to use for rendering each taxonomy
    page. This template will be rendered with additional taxonomy data (see
    below). Defaults to `_TAXONOMY.html`, where `TAXONOMY` is the taxonomy name
    (as specified above in the `taxonomy` setting).

* Required routing parameters:
  * `TAXONOMY`, where `TAXONOMY` is the name of the taxonomy (as specified in
    the `taxonomy` setting).


### Taxonomy configuration

Taxonomies are defined under `site/taxonomies` in the website configuration:

    site:
        taxonomies:
            tags:
                multiple: true
                term: tag

These settings should be defined as a map. Each entry is the name of the
taxonomy, and is associated with the settings for that taxonomy. Settings
include:

* `multiple`: Defines whether a page can have more than one value assigned for
  this taxonomy. Defaults to `false` (_i.e._ only a single value can be
  assigned).

* `term`: Taxonomies are usually named using plural nouns. The `term` setting
  lets you define the singular form, which is used in multiple places.

### Template data

When the taxonomy generator renders your _index page_, it will pass it the
following layout template data:

* `<taxonomy_name>` (the taxonomy name) will contain the term, or terms, for the
  current listing. For instance, for a "_tags_" taxonomy, it will contain the
  list of tags for the current listing. In 99% of cases, that list will contain
  only one term, but for "_term combinations_" (i.e. listing pages tagged with
  2 or more tags), it could contain more than one. For taxonomies that don't
  have the `multiple` flag, though, that template data will only be a single
  term (_i.e._ a string value).

* `pagination.items` will list the classified content, _i.e._ content from the
  generator's `source`, filtered for only content with the current term. For
  instance, the list of blog posts with the current tag or category or whatever.
  Note that this is still pagination data, so it will create _sub-pages_.


## Blog archives source

This source will generate one page per year for a given source of pages. This
is useful for generating a "blog archive" section.

* Type: `blog_archives`

* Configuration Settings:
  * `source`: The name of a source from which to look for dated content.
  * `template`: The name of a layout template to use for rendering each year
    page. The template will be rendered with additional data (see below).
    Defaults to `_year.html`.

* Required routing parameters:
  * `year`


### Template data

When the blog archives source renders your _index page_, it will pass it the
following template data:

* `year` is the current year.

* `pagination.items` lists the content dated for the current year, in
  reverse-chronological order. This will potentially create _sub-pages_ since
  this is pagination data.

* `archives` lists the same thing as `pagination.items`, but without paginating
  anyting, _i.e._ even if you have _lots_ of blog posts in a given year, they
  will all be listed on the same page, instead of being listed, say, 10 per
  page, with _sub-pages_ created for the rest. Also, `archives` will list posts
  in chronological order.

