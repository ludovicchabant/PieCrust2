---
title: Themes
---

Themes let you change your website's appearance easily by applying a new set of
templates, layouts, and styles over you content. You're probably already
familiar with this concept if you're coming from some other CMS like WordPress.

In PieCrust, themes work better if you don't have any templates -- otherwise,
you would end up mixing the theme's appearance with your own, which (unless it
was done specifically against a given theme) probably won't work well.

Themes are really just normal PieCrust websites, but with a `theme_config.yml`
file instead of `config.yml`. You can easily install them, change them, or
create your own.


{% for part in family.children -%}
* [{{part.title}}]({{part.url}})
{% endfor %}

