---
title: "Appendix 7: Asset Processors"
short_title: "Asset Processors"
---

Here's a list of the PieCrust pipeline's asset processors that ship with
PieCrust by default.

Configuration settings for asset processors must be defined in the website
configuration, unless noted otherwise.


## CleanCSS

Compresses CSS files using the `cleancss` utility.

Name: `cleancss`

Configuration settings (under `cleancss/`):

* `bin`: The name or path of the `cleancss` executable. Defaults to `cleancss`,
  which means it's expected you have it in your `PATH`.

* `options`: A list of miscellaneous options to pass to `cleancss`. Defaults to
  `--skip-rebase`.


## Compass

A processor that runs `compass` as part of the bake.

Name: `compass`

Configuration settings (under `compass/`):

* `enable`: This processor is disabled by default. You need to set this
  setting to `true`.

* `bin`: The name or path of the `compass` executable. Defaults to `compass`,
  which means it's expected you have it in your `PATH`.

* `frameworks`: The list of frameworks to enable.

* `options`: A list of miscellaneous options to pass to `compass`. You can use
  the placeholders `%out_dir%` and `%tmp_dir%` to refer to the temporary and
  output directories of the current bake.

Notes:

* It's expected that the Compass configuration file is called `config.rb` and is
  located in your website's root directory.

* To troubleshoot any problems, run `chef` with the `--debug` option to see the
  full command-line invocation of `compass`.


## Concat

A simple processor that concatenates multiple other files.

The input for this processor must be a `.concat` file whose file name without
the `.concat` extension will be the output file name. The contents must be a
YAML configuration that lists the files to concatenate.

So for instance, a `foo.js.concat` file will generate an output file named
`foo.js`. If the concents of the `.concat` file are the same as below, it will
end up being the concatenation of files `something.js` and `lib/vendor/blah.js`:

    files:
        - foo.js
        - lib/vendor/blah.js

Other settings are possible in the YAML file:

* `path_mode`: Either `relative` or `absolute`. If `relative`, the `files` list
  specifies files relative to the `.concat` file. Otherwise, they're relative to
  the asset root directory.

* `delim`: The delimiter string to use between each concatenated file. Defaults
  to a line feed (`\n`).


## Copy

A simple processor that copies the input file to the same place (relative to the
asset directory, and to the output directory).

Name: `copy`


## LessCSS

Converts LESS CSS files into normal CSS.

Name: `less`

Configuration settings (under `less/`):

* `bin`: The name or path of the `lessc` executable. Defaults to `lessc`,
  which means it's expected you have it in your `PATH`.

* `options`: A list of miscellaneous options to pass to `lessc`. Defaults to
  `--compress`.


## Sass

Converts Sass files (`.scss`, `.sass`) into normal CSS.

Name: `sass`

Configuration settings (under `sass/`):

* `bin`: The name or path of the `scss` executable. Defaults to `scss`,
  which means it's expected you have it in your `PATH`.

* `style`: The output CSS style. Defaults to `nested`.

* `load_paths`: A list of additional include paths. Defaults to an empty
  list.

* `options`: A list of miscellaneous options to pass to `lessc`. Defaults to
  an empty list.


## Sitemap

Creates a Sitemap file by transforming a `.sitemap` file into a `.xml` file of
the same name with contents that match the Sitemap specification.

The `.sitemap` must be a YAML file (_i.e._ something a bit like the website
configuration file) that can contain either:

* `locations`: A list of locations to include in the Sitemap file. Each location
  must have a `url` setting. Optionally, they can have a `lastmod`,
  `changefreq`, and/or `priority` setting. This is basically boiling down to
  writing the Sitemap in YAML instead of XML.

* `autogen`: This should be a list of page source names for which to
  auto-generate the Sitemap. Each source listed here will have all its pages
  included in the Sitemap. The `url` and `lastmod` of each entry will be set
  accordingly to their corresponding page. Each page can define a `sitemap`
  configuration setting to override or add to the corresponding entry.
  

## UglifyJS

Compresses Javascript files using the `uglifyjs` utility.

Name: `uglifyjs`

Configuration settings (under `uglifyjs/`):

* `bin`: The name or path of the `uglifyjs` executable. Defaults to `uglifyjs`,
  which means it's expected you have it in your `PATH`.

* `options`: A list of miscellaneous options to pass to `uglifyjs`. Defaults to
  `--compress`.

