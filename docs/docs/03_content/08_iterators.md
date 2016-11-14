---
title: Iterators
needs_pygments: true
---

PieCrust returns _iterator objects_ as template data in several cases:
`pagination.posts`, `assets`, `site.pages`, etc. Any time there's a list
of _stuff_, you can bet it's returned as an _iterator object_.

At first glance, there's not much difference with a simple list:

{%highlight 'django'%}
{%raw%}
{% for page in site.pages %}
* [{{page.title}}]({{page.url}})
{% endfor %}
{%endraw%}
{%endhighlight%}

But the iterator includes features that, although they can be emulated with
enough templating code, are much faster to achieve with the shortcut functions
available here.

For example, if you want to get the first 10 pages that have the tag `pastry`,
you can do this:

{%highlight 'jinja'%}
{%raw%}
{% for page in site.pages.has_tags('pastry').limit(10) %}
* [{{page.title}}]({{page.url}})
{% endfor %}
{%endraw%}
{%endhighlight%}

You can even achieve more elaborate filtering with the [filter syntax][flt],
too.

[flt]: {{docurl('content/filtering')}}

