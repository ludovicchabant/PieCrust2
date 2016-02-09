---
title: Publishing
---

> PieCrust can be used either as a static website generator or as a dynamic CMS.
> **This section is about using the static generation feature to publish a
> completely static website**. For how to deploy a PieCrust website as a dynamic
> CMS, see the [deployment documentation][deploy].

To publish your website, you need to "_bake_" it, and then place the output of
this bake on a public server somewhere.


## Baking

When you "_bake_" your website, PieCrust will generate all the pages, posts,
assets, and other pieces of content you made into simple files on disk. To do
this, simply run:

    $ chef bake

You should see some information about how many pages PieCrust baked, how much
time it took to do so, etc. Without any arguments, the output is placed inside
the `_counter` directory at the root of your website.

You can specify another output directory:

    $ chef bake -o /path/to/my/output

For other parameters, refer to the help page for the `bake` command by running
`chef help bake`.

At this point, you only need to copy or upload the output files (everything
inside `_counter`, or whatever other output directory you specified) to a place
where people will be able to access them. This is typically a public directory
on machine that will serve it _via_ HTTP using software like [Apache][] or
[Nginx][].


## Publishing

PieCrust is also capable of publishing your website more or less automatically
for the most common types of setup. This is done with the `publish` command.

You can specify various "_publish targets_" in your website configuration. By
default, a target will first bake your website into a temporary directory, and
then execute some steps that depend on the target type.

For example, the following configuration has one target (`upload`) that runs
`rsync` to copy the output of the bake to some web server:

```
publish:
    upload:
        type: rsync
        destination: user@example.org:/home/user/www
```

You can then run:

```
$ chef publish upload
Deploying to upload
[   863.1 ms] baked 4 user pages.
[     5.3 ms] baked 1 theme pages.
[    79.2 ms] baked 0 taxonomy pages.
[    84.8 ms] processed 3 assets.
[  1210.9 ms] Baked website.
building file list ... done

sent 29965 bytes  received 20 bytes  19990.00 bytes/sec
total size is 22189128  speedup is 740.01
[   991.5 ms] Ran publisher rsync
[  2203.3 ms] Deployed to upload
```

Of course, the output will vary based on your website, your target, whether you
previously published that target or wiped the PieCrust cache, etc.

For more information about the different types of publish targets available in
PieCrust, refer to the [publishers reference][pubs].


[deploy]: {{docurl('deploying')}}
[pubs]: {{docurl('reference/publishers')}}
[apache]: http://httpd.apache.org/
[nginx]: http://nginx.org/

