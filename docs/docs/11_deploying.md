---
title: Deploying
---

PieCrust can be used either as a static website generator or as a dynamic CMS.
This section is about deploying a PieCrust website as a dynamic CMS. For how to
bake a website and publish it statically, see the [publishing
documentation][publish].

Using PieCrust as a dynamic CMS requires setting up a web server to execute code
and serve requests. PieCrust itself can be wrapped in a [WSGI
application][wsgi], so there are many different ways to do it. The following
ways have been tested to work, and should perform very well in a production
environment:

{% for p in family.children %}
* [{{p.title}}]({{p.url}}): {{p.summary}}
{% endfor %}

[publish]: {{docurl('publishing')}}
[wsgi]: https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface

