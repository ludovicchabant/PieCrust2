---
title: Plugin Components
---

Once you've [created a plugin][1], you need to make it provide new _components_.

{% for comp in family.children -%}
* [{{comp.title}}]({{comp.url}})
{% endfor %}

[1]: {{apiurl('plugins')}}

