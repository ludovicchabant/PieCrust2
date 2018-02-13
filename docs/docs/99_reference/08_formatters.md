---
title: "Appendix 8: Formatters Reference"
short_title: Formatters Reference
---

When a page gets rendered, it goes through a formatter, _i.e._ something that
can translate whatever syntax you used into the syntax you want the output to
be. In 99% of cases, the syntax will be something like Markdown or Textile, and
the output will be HTML.

Here is a list of the formatters that come with PieCrust out of the box.


## Markdown

Name: `markdown`

[Markdown][] is a lightweight markup language that makes it easy to write HTML.
For a primer on its syntax, see the [original documentation][gruber].

The default Markdown formatter in PieCrust is powered by
[Python-Markdown][pymd], which works well and has a good number of available
extensions. You can enable those Markdown extensions in your website
configuration like this:

```
markdown:
  extensions: name,name,name
```

The available extension names for Python-Markdown can be found [here][ext]. The
name to use is the last piece in the list, so for example the "_Fenced Code
Blocks_" extension would be enabled with `fenced_code`.

> For a vast performance improvement, you can install the `PieCrust-Hoedown`
> plugin which uses a native (_i.e._ written in C) implementation of Markdown.
> It may not be available for your system however, which is why it doesn't ship
> by default with PieCrust.


## Textile

Name: `textile`

[Textile][] is another lightweight markup language to write HTML. It has more
features than Markdown (see above) but is also more complicated. You can refer
to [this documentation][tx] to learn the syntax.


[markdown]: https://en.wikipedia.org/wiki/Markdown
[gruber]: https://daringfireball.net/projects/markdown/syntax
[pymd]: https://python-markdown.github.io/
[ext]: https://python-markdown.github.io/extensions/
[textile]: https://en.wikipedia.org/wiki/Textile_%28markup_language%29
[tx]: https://txstyle.org/

