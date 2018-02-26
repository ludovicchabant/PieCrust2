---
title: Deploying the Administration Panel
---

Deploying the administration panel to your online server will let you, well,
administrate your website. This has a few benefits, like letting you create and
edit blog posts while on the move, from a browser or from client apps that
support it. Downsides of course include a more complicated server setup, and
security risks.

The administration panel is a [Flask][] application, so the [Flask deployment
documentation][flask_deploy] applies here as well.

[flask]: http://flask.pocoo.org/
[flask_deploy]: http://flask.pocoo.org/docs/0.12/deploying/


## WSGI Application

The first thing to do is to make the WSGI application that will be served by
your web server. Create a `.wsgi` file with the following contents:

```
from piecrust.wsgiutil import get_admin_app
application = get_admin_app('/path/to/website')
```

It might be a good idea to log any application errors, at least at first, to
a log file that you can inspect if there's a problem:

```
import logging
from piecrust.wsgiutil import get_admin_app

application = get_admin_app(
    '/path/to/website',
    log_level=logging.INFO,
    log_file='/path/to/logfile.log')
```


## `mod_wsgi` (Apache)

You can follow the steps from the [Flask documentation for
Apache][flask_apache].

Here are a few things to watch our for however.

* In the `WSGIDaemonProcess` directive, you can specify a Python home directory to
  use, which is useful if you are using a virtual environment to not have to
  install PieCrust in your system's Python environment.

* You need to set `WSGIPassAuthorization` to `On` for client apps to be able to
  correctly authenticate with your website.

* Alias the administration panel's static files to the `/static` sub-folder so
  that all the CSS and pictures show up correctly. Don't forget to also set the
  proper access for Apache.

For example:

    WSGIDaemonProcess piecrust_admin user=www-data threads=4 \
                      python-home=/path/to/virtualenv
    WSGIScriptAlias /pc-admin /path/to/wsgi/file.wsgi
    WSGIPassAuthorization On
    Alias /pc-admin/static /path/to/virtualenv/lib/site-packages/piecrust/admin/static

    <Directory /path/to/wsgi>
      Require all granted
    </Directory>

    <Directory /path/to/virtualenv/lib/site-packages/piecrust/admin/static>
      Require all granted
    </Directory>

The rest is pretty much the same as what the Flask documentation says.


[flask_apache]: http://flask.pocoo.org/docs/0.12/deploying/mod_wsgi/


## Using Client Applications

The PieCrust administration panel supports the [Micropub][] protocol, so
applications like [Micro.blog][mb] can be used to create new blog posts.

This however requires you to specify ways to authenticate yourself as the owner
of your website. Thankfully, this is done quite easily with the [IndieAuth][]
protocol:

* Add some markup to your website's `<head>` section so that you point to, say,
  your Twitter profile with a `rel="me"` attribute.
* Add some authorization endpoints that handle all the security handshaking
  stuff.

For instance:

    <link href="https://twitter.com/yourusername" rel="me" />
    <link rel="authorization_endpoint" href="https://indieauth.com/auth">
    <link rel="token_endpoint" href="https://tokens.indieauth.com/token">

Make sure your Twitter profile has a link that points back at your website.
That's it!

Now you need to indicate to client applications what to do to make new blog
posts. You also do this by adding an entry in your `<head>` section:

    <link rel="micropub" href="https://your-website.com/pc-admin/micropub">

That's it too!


[mb]: https://micro.blog/
[micropub]: https://en.wikipedia.org/wiki/Micropub_(protocol)
[indieauth]: https://indieauth.com/
