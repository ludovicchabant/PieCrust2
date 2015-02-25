---
title: Website Configuration
---

A PieCrust website can be configured by editing the `config.yml` file. This file
uses the [YAML][] syntax, which should be mostly straightforward:

    site:
        title: My Fancy Blog
        author: Ludovic
        pretty_urls: true
        posts_per_page: 10
    myblog:
        something: foo
        whatever: blah

The above example defines two sections, `site` and `myblog`, with a bunch of
settings inside them. Sections can be nested at will, and settings can also be
defined at the root level. YAML is clever enough to convert things properly,
like `true` and `false` being converted to boolean values, or numbers being
treated as such.

> Sometimes you may want to use some special characters like `&` or `'`, which
> are used for advanced things in YAML. If that ever causes some YAML parsing
> errors, just add double quotes around the setting.

By convention, PieCrust's core systems only look for settings in the `site`
section. Other settings, like formatter or template engine specific settings,
will be found in other sections.

You can see all the available settings on the [website configuration reference
page][wc]

[yaml]: http://en.wikipedia.org/wiki/YAML
[wc]: {{docurl('reference/website-configuration')}}

