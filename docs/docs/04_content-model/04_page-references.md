---
title: Page References
---

There are a few places in PieCrust where you need to specify a reference to a
page -- like for instance when defining taxonomies and specifying a custom index
page.

Page references are written using the following format:

    source_name:path/to/page.ext

This means:

* `source_name`: The source in which to find the page.

* `path/to/page`: A _source path_ to the page. This is usually just a
  file-system relative path, starting from the file-system endpoint of the
  source, but some sources may have slightly different ways to specify a
  relative path. Refer to the source's documentation.

* `.ext`: The extension to use. If you want to the user to have some freedom in
  the matter -- like for example letting the user use either a `.md` or
  `.textile` extension to use either Markdown or Textile syntax -- then you can
  use `.%ext%`. This will match any extension registered in the
  `site/auto_formats` settings (see the [formatters documentation][fmt]).


### Multiple matches

It's possible to define a reference that will match multiple possible pages --
in this case, it would resolve to the first found page. Just write additional
page references, using `;` as a separator.

For instance:

    foo:something/whatever.md;bar:someting.md

...would match `something/whatever.md` in source `foo` if it exists, otherwise
it would match `something.md` in source `bar` if it exists. Otherwise, the page
isn't found.

This is especially useful for falling back to a page defined in a theme.

[fmt]: {{docurl('content/formatters')}}

