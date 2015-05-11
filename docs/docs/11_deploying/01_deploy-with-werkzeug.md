---
title: Deploy with Werkzeug
summary: Using Werkzeug with Apache
---

Werkzeug is an HTTP and WSGI toolkit for Python that PieCrust uses to run the
preview server when you invoke `chef serve`. It can be used to serve PieCrust
using the very popular Apache web server, but has several other ways to work, as
listed on the [Werkzeug application deployment documentation][2].

Whether you'll be using [`mod_wsgi`][3] or [FastCGI][4], you'll need a WSGI
application for your PieCrust website. This is how you do it:

```
from piecrust.wsgiutil import get_app
application = get_app('/path/to/website/rootdir')
```

You can then follow the rest of the Werkzeug deployment instructions, which
mostly includes setting up an Apache configuration section for your website.


[1]: http://werkzeug.pocoo.org/docs/0.10/
[2]: http://werkzeug.pocoo.org/docs/0.10/deployment/
[3]: http://werkzeug.pocoo.org/docs/0.10/deployment/mod_wsgi/
[4]: http://werkzeug.pocoo.org/docs/0.10/deployment/fastcgi/

