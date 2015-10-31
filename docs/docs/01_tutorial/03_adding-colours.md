---
title: "Part 3: Adding Colours"
---

In the first two parts of this [tutorial][tut], we created a simple blog website
and added some content. In the third part, we'll take a look at PieCrust's 
[built-in asset pipeline][pip].


## Stylesheets

Edit the `templates/default.html` layout and delete the whole part between
`{%raw%}{% if site.css %}{%endraw%}` and `{%raw%}{% endif %}{%endraw%}`. Replace
it with:

```htmldjango
{% raw %}
<link rel="stylesheet" type="text/css" href="{{ site.root }}myblog.css"/>
{% endraw %}
```

Now create the file `assets/myblog.css`. Leave it empty for now. If you're not
running `chef serve` anymore, run it again.

Refresh you browser, and you should see your blog revert to your browser's
default styles. You should also see, in the `chef serve` command output in your
terminal, an entry that shows that it processed `myblog.css`:

```
[    26.1 ms] processed 1 assets.
```

Now start writing some CSS code in the empty file:

```css
body {
    font-family: sans-serif;
    color: #FF481C;
    background: #063B76;
}

a {
    color: #083D78;
    text-decoration: none;

    &:hover {
        text-decoration: underline;
    }
    &:visited {
        color: #74AC00;
    }
}

#container {
    width: 640px;
    margin: 0 auto;
}
```

When you save, you should see that PieCrust picks it up right away and copies it
to a place that your browser can fetch it from. In this case, only copying is
needed because it's a simple CSS file, but if it was a [LessCSS][] or
[Sass][] file, it would run the appropriate compiler. The same applies for
any other type of file for which PieCrust has a "processor" defined. Otherwise,
it just copies the file.

Refresh your browser, and you should see the same blog with a completely
different look. You can go back to the CSS file and work some more on it -- by
the time you've swtiched back to your browser and pressed `F5`, PieCrust has
typically finished processing the updated file.


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
That's all fine! PieCrust won't do anything about all those directories unless
you ask it to.


## Next steps

In the fourth part of this tutorial, we'll look at how we can [publish this
magnificent blog][part4].


[tut]: {{docurl('tutorial')}}
[pip]: {{docurl('asset-pipeline')}}
[procs]: {{docurl('reference/asset-processors')}}
[part4]: {{docurl('tutorial/making-it-public')}}
[lesscss]: http://lesscss.org/
[sass]: http://sass-lang.com/
[npm]: https://www.npmjs.com/
[bower]: http://bower.io/

