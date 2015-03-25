---
title: Sources
---

_Sources_ are the part of a content model that specifies where PieCrust will
find your content. This is done in the website configuration:

    site:
        sources:
            foo:
                type: posts/flat
            bar:
                type: default

As shown above, the `site/sources` setting must contain a map of the sources you
want: each source's name, followed by its settings.

Usually, a source will be a directory in the website's root directory, in which
you'll put text files often following some kind of naming convention.

Source settings depend on the _type_ of the source, but all sources have some
common settings. All settings are optional except for `type`.

* `type`: This defines what kind of backend you want for a source. See the [list
  of sources][refsrc] for the source types that ship with PieCrust. You can also
  get more source types by installing plugins.

* `fs_endpoint`: Most sources will read their data from the file-system. By
  default, the file-system directory will be a sub-directory of the website's
  root with the same name as the source's name. This can be customized with the
  `fs_endpoint` setting, which is specified relative to the website root.

* `data_endpoint`: Most sources will also want to expose all their pages to a
  template data endpoint, so you can easily iterate on them -- for example to
  show an archive or a site map. By default, this endpoint is the same as the
  source's name, but it can be customized with the `data_endpoint` setting.

* `data_type`: The data that's exposed through the `data_endpoint` is an
  `iterator` by default, which means it's a simple flat list of pages. There are
  other possible forms, like for example a blog archive, which is a bunch of
  different iterators rolled into the endpoint, with easy ways to list pages by
  year or by month.

For an example of sources configuration, see the [default content model][def].

[refsrc]: {{docurl('reference/sources')}}
[def]: {{docurl('content-model/default-model')}}

