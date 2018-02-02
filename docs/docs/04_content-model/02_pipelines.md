---
title: Pipelines
---

Content pipelines are what PieCrust uses to actually process articles and assets
and other pieces of content into a static website, or whatever else if the
desired output.

The two main pipelines that come with PieCrust are the "page" pipeline and the
"asset" pipeline.


## Page pipeline

PieCrust loads pages from [page sources][src], which are most of the time a
sub-directory of your website's root directory, with a bunch of text files in
them. For an [out-of-the-box PieCrust website][def], these are the `pages/` and
`posts/` directories, which contain pages and blog posts respectively.

Each page or post goes through the following process:

1. Templating
2. Formatting
3. Layout rendering

The first two steps render the page's contents, which can be split into [content
segments][seg]. Most of the time, a page will only have one content segment,
appropriately called `content`. The third step optionally inserts these contents
into a re-usable piece of markup.

Let's assume you have this in `pages/recipes.md`:

    ---
    title: All Recipes
    layout: simple
    ---
    This page lists all the recipes written so far in {{site.title}}:

    {%raw%}
    {% for p in family.children %}
    * [{{p.title}}]({{p.url}})
    {% endfor %}
    {%endraw%}


### Templating

Each segment first goes through [templating][tpl]. Various pieces of data will
be exposed to the template engine for you to use in your page -- the page's
configuration settings, the website's configuration settings, utilities to
create paginated content, access points to all pages or blog posts, etc.

The default template engine is [Jinja][].

If the `site/title` setting was set to "_Ludovic's Blog_" in the `config.yml`
file, and there are a couple of recipe pages inside `pages/recipes/`, the
`recipes.md` page will come out of the templating phase like this:

    This page lists all the recipes written so far in Ludovic's Blog:

    * [Rhubarb Pie](/recipes/rhubarb-pie)
    * [Pound Cake](/recipes/pound-cake)

### Formatting

Next, the result goes through a [formatter][fmt], which will convert the
intermediate text into the final text.

The default formatter is [Markdown][]. So our page becomes:

```html
<p>This page lists all the recipes written so far in Ludovic&#8217;s Blog:</p>
<ul>
<li><a href="/recipes/rhubarb-pie">Rhubarb Pie</a></li>
<li><a href="/recipes/pound-cake">Pound Cake</a></li>
</ul>
```


### Layout rendering

Last, the page's templated and formatted contents are put inside a _layout_
(unless the page's `layout` configuration setting is set to `none`). Since our
example page is using the `simple` layout, and if we assume the file
`templates/simple.html` looks like this:

```htmldjango
{%raw%}
<html>
<head><title>{{page.title}}</title></head>
<body>
{{content|safe}}
</body>
</html>
{%endraw%}
```

...then our final page will be:

```html
<html>
<head><title>All Recipes</title></head>
<body>
<p>This page lists all the recipes written so far in Ludovic&#8217;s Blog:</p>
<ul>
<li><a href="/recipes/rhubarb-pie">Rhubarb Pie</a></li>
<li><a href="/recipes/pound-cake">Pound Cake</a></li>
</ul>
</body>
</html>
```

Of course, we glossed over a lot of things here, which you will want to learn
about:

* [Site configuration settings][siteconf].
* [Page configuration settings][pageconf].
* [Templating][tpl], and [Jinja's syntax][jinja].
* [Formatting][fmt], with [Markdown][] or [Textile][].


## Asset pipeline

PieCrust comes with a very capable built-in asset pipeline to process your CSS
and Javscript files, images, etc. It works very well for common use-cases, since
it doesn't require any kind of configuration -- unlike other more powerful
systems like [Grunt][] or [Gulp][].

The PieCrust asset pipeline matches files to *processors*, in a recursive way --
which means the _outputs_ of a given processor are then potentially re-processed
by others processors.

For instance, if you have a [Less CSS file][less], it will be processed like so:

    foo.less   ->   foo.css  ->  foo.min.css

Any LessCSS file (_i.e._ a file with the `.less` extension) will be compiled with
the LessCSS processor, which outputs a CSS file. This then gets picked up by
the CleanCSS processor, which will generate a compressed CSS file.

If you want more information about what processors are mapped to what file
types, you can check the list of [built-in processors][procs]. There's also more
information available about the [asset pipeline][pipe].


[src]: {{docurl('content-model/sources')}}
[ppl]: {{docurl('content-model/pipelines')}}
[def]: {{docurl('content-model/default-model')}}
[seg]: {{docurl('content/content-segments')}}
[tpl]: {{docurl('content/templating')}}
[fmt]: {{docurl('content/formatters')}}
[pipe]: {{docurl('asset-pipeline')}}
[procs]: {{docurl('reference/asset-processors')}}
[siteconf]: {{docurl('general/website-configuration')}}
[pageconf]: {{docurl('content/page-configuration')}}
[jinja]: http://jinja.pocoo.org/docs/dev/templates/
[markdown]: https://en.wikipedia.org/wiki/Markdown
[textile]: https://en.wikipedia.org/wiki/Textile_(markup_language)
[grunt]: http://gruntjs.com/
[gulp]: http://gulpjs.com/
[less]: http://lesscss.org/

