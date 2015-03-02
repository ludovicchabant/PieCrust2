---
title: "Part 3: Adding Colours"
---

In the first two parts of this [tutorial][tut], we created a simple blog website
and added some content. In the third part, we'll take a look at PieCrust's
[built-in asset pipeline][pip].


## Stylesheets with Less

Edit the `templates/default.html` layout and delete the whole part between
`{%raw%}{% if site.css %}{%endraw%}` and `{%raw%}{% endif %}{%endraw%}`. Replace
it with:

    <link rel="stylesheet" type="text/css" href="{{ site.root }}myblog.css"/>

Now create the file `assets/myblog.less`. Leave it empty for now.

> __*Important*__: If you still had the `chef serve` command running since the
> beginning of the tutorial, restart it now by pressing `CTRL+C` and running it
> again. This is because we want it to monitor the new `assets/` folder you just
> created.

Refresh you browser, and you should see your blog revert to your browser's
default styles. You should also see, in the `chef serve` command output in your
terminal, an entry that shows that it processed `myblog.less`.

Now start writing some Less CSS code in the empty file (you can learn more about
the Less CSS syntax on the [official website][less]):

    @color-primary: #FF481C;
    @color-secondary1: #083D78;
    @color-secondary2: #CBF66E;
    @color-secondary2-dark: #74AC00;

    body {
        font-family: sans-serif;
        color: @color-primary;
        background: darken(@color-secondary1, 20%);
    }

    a {
        color: @color-secondary2;
        text-decoration: none;

        &:hover {
            text-decoration: underline;
        }
        &:visited {
            color: @color-secondary2-dark;
        }
    }

    #container {
        width: 640px;
        margin: 0 auto;
    }

When you save, you should see that PieCrust picks it up right away and compiles
the Less file into a CSS file that your browser can fetch.

Refresh your browser, and you should see the same blog with a completely
different look. You can go back to the Less file and work some more on it -- by
the time you've swtiched back to your browser and pressed `F5`, the Less
compiler should have already finished.


## More assets

You can start making more assets for your website -- logos, background pictures,
Javascript animations, etc. All those files will, if put in the `assets/`
directory, be processed by PieCrust and ready to be previewed or baked.

For more information about the available asset processors in PieCrust, you can
checkout the documentation about the [asset pipeline][pip] and the [asset
processors reference][procs].

### Using PieCrust with other tools

Because PieCrust, at this point, only cares about the `assets/`, `templates/`,
`pages/` and `posts/` directories, you can create any other directories in your
website's root to put whatever you need.

For example, it's common these days to use a package manager like [npm][] or
[Bower][] to download libraries and utilities to use with a given website. Those
will create directories of their own, like `node_modules/` and
`bower_components`, along with root files like `package.json` and `bower.json`.
That's all fine!


## Next steps

In the fourth part of this tutorial, we'll look at how we can [publish this
magnificent blog][part4].


[tut]: {{docurl('tutorial')}}
[pip]: {{docurl('asset-pipeline')}}
[procs]: {{docurl('reference/asset-processors')}}
[part4]: {{docurl('tutorial/making-it-public')}}
[less]: http://lesscss.org/
[npm]: https://www.npmjs.com/
[bower]: http://bower.io/

