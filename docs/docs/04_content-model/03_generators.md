---
title: Generators
---

Generators are like [sources][], but they procedurally generate pages based on
the rest of your site's content.

The [default content model][def] defines generators for your taxonomies (tags,
categories, or whatever else you want to classify your posts with), and one
generator for your blog archives (to generate one archive page per year).

Generators are defined in the website configuration. For example:

```
site:
  generators:
    my_archives:
      type: blog_archives
        source: posts
        page: 'page:_year.md'
```

The only required setting for a generator is the `type` setting, which specifies
what type of generator this should be. Other settings depend on the type of
generator.

To see what generators are available in PieCrust out of the box, see the
[reference page on generators][refgen].


[sources]: {{docurl('content-model/routes')}}
[refgen]: {{docurl('reference/generators')}}
[def]: {{docurl('content-model/default-model')}}

