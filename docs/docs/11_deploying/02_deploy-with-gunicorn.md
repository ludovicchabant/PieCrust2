---
title: Deploy with Gunicorn
summary: Using Gunicorn with Nginx
---

[Gunicorn][1] is a WSGI HTTP server for UNIX. It's popular with people looking
for something more lightweight -- and potentially more performant -- than
Apache, since it primarily works hand in hand with Nginx. It will, however,
require a bit more configuration work.

Using Gunicorn usually starts with running the Gunicorn server, pointing it to your
WSGI application. Although you can write a [quick WSGI script][4] to get one
pointing to your website root, there's a nice shortcut in the form of the
`piecrust.wsgiutil.cwdapp` module. It will automatically create a WSGI
application for the current directory.

So you can easily run Gunicorn without writing anything:

```
cd /path/to/website/rootdir
gunicorn piecrust.wsgiutil.cwdapp:app
```

Of course, you may want to use custom command-line parameters -- see the
documentation on [running Gunicorn][2] for more information.

After that, you can configure Nginx (or any other web server that can do HTTP
proxying) to handle requests and responses. See the documentation on [deploying
Gunicorn][3] for more information on that.


[1]: http://gunicorn.org/
[2]: http://docs.gunicorn.org/en/19.3/run.html
[3]: http://docs.gunicorn.org/en/19.3/deploy.html
[4]: {{docurl('deploying/deploy-with-werkzeug')}}

