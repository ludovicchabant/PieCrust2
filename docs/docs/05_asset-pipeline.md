---
title: Asset Pipeline
---

PieCrust comes with a simple, yet efficient, asset pipeline. If you have
advanced requirements, or want to use something familiar, you can of course use
well known systems like [Grunt][] or [Gulp][], but you should definitely give
the PieCrust asset pipeline a try.

The PieCrust asset pipeline doesn't require a build file: asset processors are
enabled more or less globally, and will affect all assets the same way inside a
given asset directory.


## Assets directories

By default, the asset pipeline will process only one assets directory, `assets/`.
You can change or add directories with the `baker/assets_dirs` setting in the
website configuration.

For each file found in an assets directory, the pipeline will either:

* Ignore it, if it matches the `baker/ignore` patterns. By default, those
  patterns include common temporary files like `.DS_Store` and `Thumbs.db`
  files, and common source control files like `.git`, `.hg`, and `.svn`.

* Process it, if it matches any of the active asset processors. The output of
  the processing phase will be put in the output directory.

* Copy it as is, if no asset processor was found. Just like for processing, the
  relative path of the asset is preserved in the output directory.


## Asset Processing

As mentioned in the previous section, each asset file will be matched against
available asset processors. Most processors will accept a file based on its
extension, although some processors use other conditions. Processors have a
priority, so for instance the `copy` processor, which accepts _all_ files, will
be matched last.

The key element however is that the PieCrust pipeline is a _multi-step_
processing pipeline. The output of the first matched processor will be itself
matched again against all the other processors... and so on, until no more
processors match and the `copy` processor copies the result to the output(s)
directory.

So for instance, if you have a LessCSS file, it will be processed like so:

    foo.less    ->    foo.css    ->    foo.min.css

The `.less` extension gets matched to the LessCSS processor, which outputs a
standard `.css` file. This file gets picked up by the CleanCSS processor, which
minifies the file, and can optionally add the `.min` suffix. There's no other
processors that can handle a `.css` file, so the resulting `foo.min.css` is
copied to the output directory.




[Grunt]: http://gruntjs.com/
[Gulp]: http://gulpjs.com/
[procref]: {{docurl('reference/asset-processors')}}

