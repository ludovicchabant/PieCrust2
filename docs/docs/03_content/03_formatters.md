---
title: Formatters
---

As explained in the documentation about [how PieCrust works][how], the page
contents that you write go through a _formatter_ before the page is rendered or
baked. PieCrust ships with 2 standard formatters: [Markdown][] and [Textile][].

The formatter used on a page is determined by the `format` setting in the
page's [configuration header][pageconf]:

    * `markdown` for Markdown
    * `textile` for Textile

If unspecified, the extension of the page file is matched against the
`site/auto_formats` setting in the [site configuration][siteconf]:

    * `.md` for Markdown
    * `.textile` for Textile

Otherwise, the `site/default_format` setting in the site configuration will be
used, and that's Markdown by default.



[how]: {{docurl('general/how-it-works')}}
[pageconf]: {{docurl('content/page-configuration')}}
[siteconf]: {{docurl('general/website-configuration')}}
[markdown]: https://en.wikipedia.org/wiki/Markdown
[textile]: https://en.wikipedia.org/wiki/Textile_(markup_language)

