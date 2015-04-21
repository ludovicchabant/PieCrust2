---
title: Importing
---

Many people come to static website generators after having been frustrated with
more full-fledged -- but paradoxically more limiting -- content management
systems like Wordpress. Others just try different static website generators
until they find one they're totally satisfied with.

PieCrust supports importing content from other such systems, using the `chef
import` command. Here are some details about each importer:

{% for part in family.children -%}
* [{{part.title}}]({{part.url}})
{% endfor %}

