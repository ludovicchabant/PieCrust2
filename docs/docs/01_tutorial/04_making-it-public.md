---
title: "Part 4: Making It Public"
---

In the first 3 parts of this [tutorial][tut], we made a pretty blog. But it's
not really worth much if nobody can see it, so here we'll talk about how we can
bake it and publish it. This is where we put the "_static_" in "_static website
generator_".


## Baking

"_Baking_" is what we call the act of transforming your pages, posts, and
layouts into static HTML files.

It's almost as if someone was to request _every possible page in your website_,
and save the result to separate HTML files whose filenames and directories match
the URL they were requested from.  This is not what happens in reality when you
bake with PieCrust, but that's fairly equivalent.

You can bake your website by simply running:

    $ chef bake
    [     2.6 ms] cleaned cache (reason: need bake record regeneration)
    [   111.6 ms] [1] about/
    [   115.1 ms] [2] feed.xml/
    [   115.7 ms] [3] 2015/my-first-post/
    [   120.0 ms] [0] /
    [    12.1 ms] [1] 2015/my-second-post/
    [     9.1 ms] [2] 2015/a-third-one/
    [    42.7 ms] [0] tag/foo/
    [    43.4 ms] [1] tag/bar/
    [    53.7 ms] [2] tag/another/
    [     5.8 ms] [0] myblog.less
    -------------------------
    [   203.9 ms] done baking

The output is obviously not going to be exactly the same (especially if you
created more content while playing around), but it should be equivalent.

The baked website is available in the `_counter/` directory.


## Publishing

Publishing a static website is a really simple matter: you just upload the
static files to a web server.

In our case, this means uploading the contents of the `_counter/` directory to
whatever place we have up there in the cloud for such a thing -- probably a
machine running an [Apache][] or [Nginx][] web server. You can use FTP/SFTP for
this, with such utilities as [Cyberduck][], [WinSCP][], or [FileZilla][].

Once your files are up, you should be able to see the same things as when you
were previewing them with `chef serve`.


[tut]: {{docurl('tutorial')}}
[apache]: https://httpd.apache.org/
[nginx]: http://nginx.org/
[cyberduck]: https://cyberduck.io/
[filezilla]: https://filezilla-project.org/
[winscp]: http://winscp.net/eng/index.php

