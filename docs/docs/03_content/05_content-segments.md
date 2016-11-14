---
title: Content Segments
---

A page file is usually split in two sections: the [configuration
header][pageconf], and the content itself:

    ---
    foo: bar
    something: else
    ---
    Content goes here.

When making a layout for a page, or inserting a page into another (like listing
blog posts), you would use `content` to get that second section.

But the contents of a page can also be split into _segments_.


## Segments

A page segment starts with the following marker:

    ---name---

You can replace `name` with something else, which will be the name of the
segment.

By default, the first segment (from the top of the file, or from just after the
configuration header if there's one) will be named `content`.

This mean you can create a page like so:

    ---
    title: Page with multiple segments
    ---
    The contents go here.

    ---sidebar---
    Sidebar goes here

You can then use, the page's layout, both the `content` and `sidebar` segments
to put each piece of text in its appropriate place.

You can also specify a [formatter][] for a given segment, by adding `:formatter`
after the segment's name. For instance, to disable formatting for the `sidebar`
segment (because you want to write pure HTML and there's no need to have
Markdown in the way):

    ---
    title: Page with multiple segments
    ---
    The contents go here.

    ---sidebar:none---
    <aside>
        Sidebar goes here
    </aside>


## Parts

You can switch formatters from one segment to the next, but you can also switch
formatters _inside_ a given segment! You can use the following marker for this:

    <--name-->

The text will be formatted with formatter `name` until the end of the current
segment, or until the end of the file.


[pageconf]: {{docurl('content/page-configuration')}}
[formatter]: {{docurl('content/formatters')}}

