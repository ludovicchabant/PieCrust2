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

Name: `markdown` or `pymarkdown`

[Markdown][] is a lightweight markup language that makes it easy to write HTML.
For a primer on its syntax, see the [original documentation][gruber].

The default Markdown formatter in PieCrust is powered by [Hoedown][], which is
fast and effective. However, is you want a more fully featured Markdown
formatter and don't mind poorer performance, you can switch to `pymarkdown`,
which uses [Python-Markdown][pymd].

You can enable Markdown extensions in your website configuration:

```
markdown:
  extensions: name,name,name
```

The available extension names can be found [here][ext1] for Hoedown, and
[here][ext2] for Python-Markdown.

In both cases, the name to use in the website configuration should be the short,
vaguely friendly name listed on the referenced webpage -- like `tables`,
`footnotes`, or `fenced_code`.


## Textile

Name: `textile`

[Textile][] is another lightweight markup language to write HTML. It has more
features than Markdown (see above) but is also more complicated. You can refer
to [this documentation][tx] to learn the syntax.


[markdown]: https://en.wikipedia.org/wiki/Markdown
[gruber]: https://daringfireball.net/projects/markdown/syntax
[hoedown]: https://github.com/hoedown/hoedown
[pymd]: https://python-markdown.github.io/
[ext1]: http://misaka.61924.nl/#extensions
[ext2]: https://python-markdown.github.io/extensions/
[textile]: https://en.wikipedia.org/wiki/Textile_%28markup_language%29
[tx]: https://txstyle.org/

