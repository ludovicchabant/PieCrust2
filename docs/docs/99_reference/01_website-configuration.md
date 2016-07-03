---
title: "Appendix 1: Site Configuration Reference"
short_title: Site Configuration
---

This is a list of the settings handled by PieCrust in the website configuration
file.


## Site section

The following settings can be set under the `site` section. The default value is
given between parenthesis:

* `auto_formats` (special, see [formatting documentation][fmt]): Specifies a list
  that maps an extension to a format name. This makes it possible to use certain
  file extensions for pages, like `.md` for Markdown content or `.textile` for
  Textile content.

* `blogs` (`['blog']`): When using the default content model, the list of blogs
  for which to create posts sources.

* `cache_time` (`28800`): Specifies the client cache time, in seconds, to
  specify in the HTTP headers.

* `category_url` (`%category%`): The URL pattern for the pages listing blog
  posts belonging to a given category. This is only meaningful if you use the
  default content model.

* `date_format` (`%b %d, %Y`): The date format to use for exposing formatted
  blog post dates to the template engine.

* `default_auto_format` (`md`): The default extension to use when creating pages
  with the `chef prepare` command.

* `default_format` (`markdown`): Specifies the default text formatter to use.

* `default_page_layout` (`default`): Specifies the default page layout when
  using the default content model.

* `default_post_layout` (`post`): Specifies the default blog post layout when
  using the default content model.

* `default_template_engine` (`jinja`): Specifies what template engine to use.

* `enable_debug_info` (`true`): If you’re using PieCrust in dynamic CMS mode,
  visitors could use the debugging features to expose potentially private
  information.  You can disable those features on the production server to
  prevent that.

* `enable_gzip` (`true`): Enables gzip compression of rendered pages if the client
  browser supports it.

* `pagination_suffix` (`/%num%`): The suffix to use for sub-pages, i.e.
  additional pages that are created when pagination is used. It must start with
  a slash, and use the `%num%` placeholder.

* `posts_fs` (`flat`): The file system organization for the blog posts. Should
  be `flat`, `shallow` or `hierarchy`, although other types exist. This is only
  meaningful if you use the default content model.

* `posts_per_page` (`5`): The number of posts to return for displaying on a
  single page. This is only meaningful if you use the default content model.

* `post_url` (`%year%/%month%/%day%/%slug%`): The URL pattern for blog posts.
  You don’t have to use all of the pattern captures (`%year%`, `%month%`,
  `%day%` and `%slug%`), but you have to at least use `%slug%`. This is only
  meaningful if you use the default content model.

* `pretty_urls` (`false`): Tells PieCrust to use URLs without a `.html` file
  extension.

* `root`: The root URL of the website. It defaults to `/`, which should be what
  you want in most cases. It will be prepended to page slugs by PieCrust in
  several places, like with the URL functions.

* `routes` (special, see [content model][cm]): Defines how URLs are parsed and
  generated for this site.

* `slugify_mode` (`encode`): Specifies how taxonomy terms (tags, categories,
  etc.) will be "_slugified_", _i.e._ turned into URL parts. The acceptable
  values detailed below, and can be combined by separating them with a comma
  (like, say, `transliterate,lowercase`):

    * `encode`: The term will be kept as-is, but non-ASCII characters (like
      accented characters and non-latin letters) will be percent-encoded. Modern
      browsers will usually show the decoded version however so it will look
      natural in the address bar.
    * `transliterate`: The term will be converted to ASCII, which means any
      accented or non-latin character will be tentatively replaced with an
      unaccented latin character.
    * `lowercase`: Convert the term to lower-case.
    * `dot_to_dash`: Convert dots to dashes.
    * `space_to_dash`: Convert spaces to dashes.

* `sources` (special, see [content model][cm]): Defines the page sources that
  define where the site's contents are located.

* `tag_url` (`tag/%tag%`): The URL pattern for the pages listing blog posts
  tagged with a given tag. This is only meaningful if you use the default
  content model.

* `taxonomies` (special, see [content model][cm]): Defines the taxonomies usable
  by pages in this site.

* `templates_dirs` (empty): Specifies additional template directories besides
  `templates`. It can either be a single path, or an array of paths. Paths are
  relative to the root directory. If the default path (`templates`) doesn't
  exist, it is simply ignored.

* `trailing_slash` (`false`): If true, and `pretty_urls` is also true, PieCrust
  will generate links to other pages with a trailing slash, thus preventing
  redirection by the web server.

* `use_default_content` (`true`): If true, the default content model (_i.e._
  pages, posts, and tags and categories as taxonomies) will be always appended
  to whatever custom sources and taxonomies are defined by the user. By setting
  this to `false`, PieCrust starts from scratch, with no content sources
  whatsoever. See the documentation on the [content model][cm].

[fmt]: {{docurl('content/formatters')}}
[cm]: {{docurl('content-model')}}


## Preparation

The following settings are under the `prepare` section, and are used by the
`chef/prepare` command.

* `editor`: The path to an editor executable to run after creating a page with
  the `chef prepare` command. By default, PieCrust will pass the path of the new
  page as an argument to the executable. If you want more control over the
  generated command line, use the `%path%` token in the value -- it will be
  replaced with the path of the new page and nothing else will be passed.

* `editor_type` (`exe`): The type of executable specified in the
  `prepare/editor` setting. Values can be:
  
      * `exe`: the command is run as an executable. This is the default.
      * `shell`: the command is run through the shell, in case you need
        environment variable expansion and other shell features.


## Baker

The following settings are under the `baker` section, and are used by the `chef
bake` command:

* `assets_dirs` (`assets`): The name(s) of the directory(ies) on which to run
  the built-in asset pipeline.

* `force` (`[]`): Patterns to use for always forcing re-processing of some
  assets with the built-in asset pipeline.

* `ignore` (`[]`): Patterns to use for ignoring certain assets with the built-in
  asset pipeline. Patterns are either glob-like (_i.e._ using wildcards) or
  regex-like (when the pattern starts and ends with a slash).

    Some patterns will always be added to the list: `_cache`, `_counter`,
    `theme_info.yml`, `.DS_Store`, `Thumbs.db`, `.git*`, `.hg*`, and `.svn`.

* `is_baking` (`false`): This setting is read-only, and will be set to true
  while baking the website (_i.e._ while the `chef bake` command is running).
  This is useful for generating things only when baking the website for
  publishing, and not while previewing (but see the `server/is_serving` setting
  too).

* `workers` (`4`): The number of threads to run for baking.


## Server

The following settings are under the `server` section, and are used by the `chef
serve` command:

* `is_serving` (`false`): This setting is read-only, and will be set to true
  while previewing the webste (_i.e._ while the `chef serve` command is running
  and the server is generating a page). This is useful for generating things
  only for preview purposes.


## Template engines

### Jinja

Settings for the Jinja template engine are under the `jinja` section:

* `auto_escape` (`true`): Turns on auto-escaping of text for safer HTML output.


## Formatters

### Markdown

Settings for the Markdown formatter are under the `markdown` section:

* `extensions` (`[]`): The list of [Markdown extensions][mdext] to enable.

[mdext]: https://pythonhosted.org/Markdown/extensions/index.html


### Smartypants

Settings for the Smartypants formatter are under the `smartypants` section:

* `enable` (`false`): Enables Smartypants on any formatter that outputs HTML.


## Asset processors

### CleanCSS

Settings for the CleanCSS processor are under the `cleancss` section:

* `bin` (`cleancss`): The path to the CleanCSS executable. By default, PieCrust
  assumes it will be in your `PATH` environment variable.

* `options` (`--skip-rebase`): Custom options and arguments to pass to the
  CleanCSS executable.


### Compass

Settings for the Compass processor are under the `compass` section:

* `bin` (`compass`): The path to the Compass executable. By default, PieCrust
  assumes it will be in your `PATH` environment variable.

* `config_path` (`config.rb`): The path to the Compass project's configuration
  file, relative to the PieCrust website's root directory.

* `enable` (`false`): Enables Compass processing for this website. This means
  that the standalone Scss/Sass processor will be disabled and replaced by the
  Compass processor.

* `frameworks` (empty): A list of Compass frameworks to enable for this website,
  either as a YAML list, or just comma-separated.

* `options` (empty): Custom options and arguments to pass to the Compass
  executable.


### LessC

Settings for the Less CSS processor are under the `less` section:

* `bin` (`lessc`): The path to the Less compiler. By default, PieCrust assumes
  it will be in your `PATH` environment variable.

* `options` (`--compress`): Custom options and arguments to pass to the Less
  compiler.


### Sass

Settings for the Scss/Sass CSS processor are under the `sass` section:

* `bin` (`scss`): The path to the Sass compiler. By default, PieCrust assumes it
  will be in your `PATH` environment variable.

* `load_paths` (empty): A list of include paths to pass to the Sass compiler.

* `style` (`nested`): The output CSS style to use.

* `options` (empty): Custom options and arguments to pass to the Sass compiler.


### UglifyJS

Settings for the UglifyJS processor are under the `uglifyjs` section:

* `bin` (`uglifyjs`): The path to the UglifyJS executable. By default, PieCrust
  assumes it will be in your `PATH` environment variable.

* `options` (`--compress`): Custom options and arguments to pass to the UglifyJS
  executable.

