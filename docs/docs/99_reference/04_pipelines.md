---
title: "Appendix 4: Pipelines Reference"
short_title: Pipelines Reference
---

Here are the content pipelines that come with PieCrust by default.


## Page pipeline

* Type: `page`

* Configuration settings:
  * `site/pretty_urls`: Whether to bake pages using a "pretty URL" path, _i.e._
    a path with no visible `.html` suffix. Defaults to `false`.
  * `baker/no_bake_setting`: The name of a setting to look for in a page, to see
    if that page should be excluded from a bake. If that setting is found, and
    is `true`, then the page is ignored. Defaults to `draft`.


## Asset pipeline

* Type: `asset`

* Configuration settings:
  * `site/SOURCE/processors`: Filters the asset processors to be used for
    content source `SOURCE`. See below.


### Processor filtering

Using the website configuration, it's possible to filter which asset processors
can be used for a given content source.

Filtering should be done with a list of processor names or patterns. Valid
processor names can be found in the [asset processor reference page][procref].
Also:

* `all`: means all processors. This is useful to start with all processors and
  exclude just a few.
* `PROCNAME`: include processor `PROCNAME`.
* `-PROCNAME`: exclude processor `PROCNAME`.


[procref]: {{docurl('reference/asset-processors')}}

