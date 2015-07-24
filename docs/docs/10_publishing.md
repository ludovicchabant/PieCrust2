---
title: Publishing
---

> PieCrust can be used either as a static website generator or as a dynamic CMS.
> **This section is about using the static generation feature to publish a
> completely static website**. For how to deploy a PieCrust website as a dynamic
> CMS, see the [deployment documentation][deploy].

## Baking

To publish your content as a static website, you need to "_bake_" it, _i.e._
generate all the pages, posts, assets, and other pieces of content:

    $ chef bake

You should then see some information about how many pages PieCrust baked, how
much time it took to do so, etc. Without any arguments, the output is located
inside the `_counter` directory at the root of your website.

You can specify another output directory:

    $ chef bake -o /path/to/my/output

For other parameters, refer to the help page for the `bake` command.

At this point, you only need to _publish_ it, _i.e._ copy or upload the output
files (everything inside `_counter`, or whatever other output directory you
specified) to a place where people will be able to access them. This is
typically a public directory on machine that will serve it _via_ HTTP using
software like [Apache][] or [Nginx][].


[apache]: http://httpd.apache.org/
[nginx]: http://nginx.org/


## Publishing

At the moment, there are no publishing features included in PieCrust -- you just
run `chef bake` as mentioned above directly on the server (pointing it to the
public directory), or locally and then upload the output via (S)FTP.

More publishing features will be included in the future.

[deploy]: {{docurl('deploying')}}

