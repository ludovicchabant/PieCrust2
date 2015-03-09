---
title: Filtering
---

The PieCrust filtering syntax can be used to select items returned by an
[iterator object][it] -- including [pagination items][pag] and [assets][ass].

Filters are _named_, and using one on an iterator object just requires to pass
that name:

{%highlight 'jinja'%}
{%raw%}
{% for page in site.pages.filter('my_filter') %}
...
{% endfor %}
{%endraw%}
{%endhighlight%}

The named filter should be available in the page's configuration header. For
instance, the following filter matches pages that have the `pastry` tag (_i.e._
a `tags` metadata value that contains `pastry`) and are not drafts (_i.e._ don't
have a `draft` metadata value set to `true`):

    ---
    title: Something
    my_filter:
        has_tags: pastry
        not:
            is_draft: true
    ---

See the [templating data reference page][tpldata] for a full list of the
available filter clauses.


[it]: {{docurl('content/iterators')}}
[pag]: {{docurl('content/pagination')}}
[ass]: {{docurl('content/assets')}}

