---
title: Importing from PieCrust 1.x
---

You can import content from a PieCrust 1.x website with:

    chef import piecrust1 /path/to/old/piecrust/website

Most of the content will be converted, but some things will still require some
manual fixes -- see below.

> ### Upgrading a website
> 
> As with all other `chef import` commands, this will import all the content
> from the old site into the current site. However, you may pass the `--upgrade`
> parameter instead of a path to a site directory to upgrade the old site
> "in-place":
> 
>     cd /path/to/old/piecrust/website
>     chef import piecrust1 --upgrade
> 
> Instead of copying and converting content into a different folder, it will
> edit your files directly.  Obviously, you need to make sure you have a backup,
> or that your website is stored in a revision control system.


## Manual fixes

### Dates

If you were using custom date formats, either in the site configuration or
through Twig filters, you'll have to convert them from [PHP date formats][php]
to [Python date formats][dt].

Note that if you need an RFC 2822 date format, you can use the `emaildate` with
Jinja as the template engine. And if you need an RFC 3339 date format (_e.g._
for XML output like RSS and Atom feeds) you can use the `atomdate` filter.

### Twig plugins

If you were using Twig plugins to add tags, filters, and functions, you'll have
to find their equivalent in Jinja.

### Clean up the asset folder

PieCrust 1.x had all assets at the website root, mixed with the special
`_content` folder. This meant that if you had some files that weren't supposed
to be baked with the site, you had to exclude them using the
`baker/skip_patterns` site configuration setting.

PieCrust 2 cleans that up a lot by having all the content at
the root, but all the assets in an `asset` folder. So if you have files that you
don't want to bake, just put them somewhere else than the `asset` folder.

However, because PieCrust has no way of knowing what's what, it will, during
import, copy everything into the `asset` folder, and convert the
`baker/skip_patterns` setting to `baker/ignore`.

Once the import process is complete, you're encouraged to move anything that
shouldn't be part of the bake out of the `assets` folder, and to remove the
uncessary `ignore` patterns. It's not required, but it will make your website a
lot tidier!


[php]: http://php.net/manual/en/function.date.php
[dt]: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior

