---
title: "Appendix 6: Publishers"
short_title: "Publishers"
---

Here's a list of website publishers that ship by default with PieCrust.

Publishers are declared and configured in the website configuration like so:

```
publish:
    <target_name>:
        type: <publisher_type>
        <config1>: <value1>
        <config2>: <value2>
```

Note that apart for the `type` setting, all publishers also share a few common
configuration settings:

* `bake` (`true`): Unless set to `false`, PieCrust will first bake your website
  into a temporary folder (`_cache/pub/<target_name>`). The publisher will then
  by default pick it up from there.

In addition to specifying publish targets via configuration settings, you can
also (if you don't need anything fancy) specify some of them via a simple
URL-like line:

```
publish:
    <target_name>: <something://foo/bar>
```

The URL-like format is specified below on a per-publisher basis.


## Shell Command

This simple publisher runs the specified command from inside your website root
directory.

* `type`: `shell`.
* `command`: The command to run.


## Rsync

This publisher will run `rsync` to copy or upload your website's bake output to
a given destination.

* `type`: `rsync`.
* `destination`: The destination given to the `rsync` executable.
* `source` (`_cache/pub/<target_name>`): The source given to the `rsync`
  executable. It defaults to the automatic pre-publish bake output folder.
* `options` (`-avc --delete`): The options to pass to the `rsync` executable. By
  default, those will run `rsync` in "mirroring" mode.

