---
title: Support
header_class: pc-support
nav_key: support
---

## Changelog

Want to know what's new with PieCrust? Check out the [CHANGELOG][ch].


## General Support

If you have a problem with PieCrust, there are a few ways to solve it:

* Check the [documentation][doc] one more time! You never know, the solution may be in
  there.
* Is the documentation wrong or missing something? If you know what must be
  fixed, you can get the source from [BitBucket][bbsrc] or [Github][ghsrc] and
  make a pull request.
* If you're pretty sure you found a bug, please file a report on
  [BitBucket][bbbug] or [Github][ghbug]. If by chance you've already fixed it,
  even better! Make a pull request, you know the drill.
* If you have questions, hit the [me][] on [Twitter][].


## Upgrading PieCrust

### Version 2 to 3

Several things have changed between version 2 and 3, and some of them introduce
breaking changes.

#### Generated page templates

Previously, taxonomy listing pages had their template defined as a page with
a special name. For instance, tag lists were by default defined by
`pages/_tag.html`.

Now those page templates are proper templates, found in the `templates`
directory (or other if you changed that). The tag list is now
`templates/_tag.html` for instance.

In general, you should only have to move your template for the `pages` folder to
the `templates` folder.

#### Generators

There is no more `generators` in the website configuration -- everything is
a content source. If you had custom generators in their, you will need to
re-declare them as standard sources.

For example, a new taxonomy source would be defined like this:

```
site:
  sources:
    post_tags:
      type: taxonomy
      taxonomy: tags
      source: posts
```

In this example, `tags` is a taxonomy declared the same way as previously inside
`site/taxonomies`, and `posts` is a normal page source declared also in the same
way as previously.


[doc]: {{docurl('')}}
[ch]: {{pcurl('support/changelog')}}
[bbsrc]: https://bitbucket.org/ludovicchabant/piecrust2
[bbbug]: https://bitbucket.org/ludovicchabant/piecrust2/issues?status=new&status=open
[ghsrc]: https://github.com/ludovicchabant/PieCrust2
[ghbug]: https://github.com/ludovicchabant/PieCrust2/issues
[me]: http://ludovic.chabant.com
[twitter]: https://www.twitter.com/ludovicchabant

