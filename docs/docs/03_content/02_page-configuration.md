---
title: Page Configuration
---

Each page can have a _configuration header_ at the top of the file, which is
used to both customize various aspects of the page, and define metadata on the
page.

The configuration header must come first in the page's file, and will be
enclosed between 2 lines with 3 dashes:

    ---
    config: goes here
    ---
    text goes here

The configuration header, just like the [website configuration][wc], is written
in [YAML][].

[yaml]: http://en.wikipedia.org/wiki/YAML
[wc]: {{docurl('general/website-configuration')}}


For example, the most common pieces of metadata to set on a page are the page's
title, and the layout template to use for it:

    ---
    title: Rhubarb Pie Recipe
    layout: recipe
    ---
    <recipe goes here>


You can see all the available settings on the [page configuration reference
page][pc], but you will probably also set lots of custom metadata on your pages.
The `title` setting is actually not used by PieCrust itself, but it's a very
common one, and it's used by the default theme.

[pc]: {{docurl('reference/page-configuration')}}

