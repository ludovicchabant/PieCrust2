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
  
  Defaults to:

  ```
  auto_formats:
    md: markdown
    textile: textile
  ```

  See the [formatters reference][fmtref] for a list of valid formatter names.

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
  See the [template engines reference][tplengref] for a list of valid engine
  names.

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
[fmtref]: {{docurl('reference/formatters')}}
[tplengref]: {{docurl('reference/template-engines')}}


## Chef Command Line

The following settings are unde the `chef` section, and all valid for _all_ chef
commands.

* `env`: A mapping of environment variables and values to set before running the
  current command. By default, variables are set to the given value. If a `+` is
  added to the variable name, the value will be _appended_ instead. The `PATH`
  variable's value is _always_ appended with either `:` or `;` depending on the
  OS.
    
    For example:

        chef:
          env:
            PATH: node_modules/.bin
            SOME_VAR: value
            "OTHER_VAR+": ",append this"


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


## Administration panel

The following settings are under `admin` and are used by the `chef serve
--admin` command, along with the administration panel that runs if you set that
up on your server.

_Nothing yet._


## Micropub endpoint

The following settings are under the `micropub` section, and are used when the
Micropub endpoint is running on your server.

* `source`: The source to create new content in when submitting new posts via
  the Micropub endpoint. Defaults to `posts`.

* `resize_photos`: The thumbnail size (in pixels) to use when receiving pictures
  via the Micropub endpoint. If set to more than 0, it will create a resized
  copy of the photo, with a `_thumb` suffix, and save it as a JPEG file.
  Defaults to 800.

* `microblogging`: A dictionary that represents a page configuration that will
  be used when a microblogging post is submitted via the Micropub endpoint.
  A post is considered as "microblogging" if it doesn't have a title. The
  typical use-case for this is to automatically set a tag or category on the
  post, so that it can be displayed differently. 

* `autocommit`: If `true`, submitted posts will be automatically committed to
  source control (if available). Currently, Mercurial and Git are supported. See
  also the "Source Control" section below. Defaults to `false`.

* `publish_target`: The publish target to run when submitting new posts via the
  Micropub endpoint.


## Source control

The following settings are under `scm`. They used by the Micropub endpoint and
the administration panel (see above).

* `author`: The author name to use when submitting new posts or pages via the
  administration panel. It's generally of the form `FirstName LastName
  <email@example.org>`.

