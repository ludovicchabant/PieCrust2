---
title: "Part 1: Your First Blog"
---

This tutorial walks you through the creation of your first PieCrust website: a
simple blog.

> Whenever you see something like this:
>
>     $ chef blah --something
>
> It means you need to run that command (starting with `chef`) in a terminal or
> command prompt. Text that doesn't start with the dollar sign is the expected
> output of the command.

We'll assume you already have installed PieCrust on your system. If not, the
installation steps are documented in the ["Getting Started"][1] page.

Let's also verify you have an up-to-date version of PieCrust.

    $ chef --version
    {{piecrust.version}}

If your version is older, you'll want to update PieCrust:

    $ pip install piecrust -U

If your version is newer, you're probably looking at old docs! You should be
able to find newer docs at the [official PieCrust website][2].


## Create the website

Creating the website can be done with a simple command:

    $ chef init myblog

This will create a directory called `myblog` in the current directory, and
initialize a PieCrust website in it. If you go inside and look at the contents,
however, you'll be surprised to find that there's not much:

    $ cd mblog
    $ ls
    config.yml

There's just a `config.yml` file! But that's the file that differentiates a
random directory with a PieCrust website. PieCrust expects a file named like
that at the root of a website.

> Because PieCrust websites are all files (mostly text), they fit really nicely
> in a source control repository. This makes it so much easier to backup and
> rollback than with a website running on an SQL database, like Wordpress.
>
> It's recommended that you create such a repository right now. If you want to
> use Git, you would type:
>
>     $ git init .
>     $ git add .
>     $ git commit -m "Initial empty blog."
>
> If you want to use Mercurial, you would type the same commands, but replace
> `git` with `hg`. For other source control systems, please check the
> documentation.
>
> And of course don't forget to commit your changes as you go!


## Preview the website

At this point, you only have an empty website, but we can still preview it in
the browser! Type:

    $ chef serve
    * Running on http://localhost:8080/

It should tell you it's started a web server at the address
`http://localhost:8080`. If you type that in your browser's address bar, you
should see PieCrust's welcome and boilerplate page.

You may notice that the `serve` command is still running. That's because the
server is still running, which is what you want. You can stop the server by
hitting `CTRL+C` at any time, but that means the preview won't work anymore. And
because we still have some work to do, obviously, you'll want to open a new
terminal or command prompt in order to type new commands.

Now let's add some stuff!


## Add some posts

To add posts, you just have to create a text file in the correct place with the
correct name. By default, PieCrust expects posts in the `posts/` directory,
with a name like so: `YYYY-MM-DD_title-of-the-post.md`.

If you're like me, you probably don't know what today's date is, however. And
there's also the risk of a typo... so let's instead use the `prepare` command:

    $ chef prepare post my-first-post
    Creating page: posts/2015-02-19_my-first-post.md

There, it tells you the path of the file it created. Open that file now in your
favorite text editor. You should see something like this:

    ---
    title: My First Post
    time: '08:21:49'
    ---
    
    This is a brand new page.

Refresh your browser, and you should see that post instead of the welcome page.
Edit the post's text (under the second `---` line), and refresh your browser.

Now let's add another post. Run the `prepare` command again:

    $ chef prepare post my-second-post
    Creating page: posts/2015-02-19_my-second-post.md

Refresh your browser, and you can see how your blog's homepage is starting to
shape up as expected, with a reverse-chronological list of your posts. That's
because the default *theme* for new PieCrust websites defines a page template
for the home page that does exactly that. This can totally be overriden, of
course, but it works well as an out-of-the-box experience.

If you want to change the title of a post, you can edit the `title:` part in the
posts' configuration header (which is what we call that part between the 2 `---`
lines). However, the URL of the post will still have `my-first-post` or
`my-second-post` in it. If you want to change that, you'd have to rename the
file itself.

> The configuration header is written in [YAML][]. It's usually fairly
> straightforward, but the first hurdle you may run into is if you want to set a
> title to something with characters like `'` or `:` in them. In this case,
> you'll have to add double-quotes (`"`) around the whole thing.
>
> If you're using a decent text editor with syntax highlighting, it should know
> about the YAML syntax and tell you that something's wrong.

Similarly, if you want to change the date of a post, you'd have to rename the
file. The time of the post is in the configuration header, though, so you can
tweak that in the text file.

To know more about the different settings you can change in a page's
configuration header, check out the [page configuration reference][pageconfref].


## Add some pages

Just like posts, pages are text files placed in some specific directory -- the
appropriately named `pages/` directory. If you create a `pages/foo.md` file,
you'll get a `/foo.html` page in your published website (or just `/foo` if you
don't want URLs ending with `.html`).

Let's create an "_About_" page for our blog. Once again, we could create the
text file "by hand" but we can also use the `prepare` command:

    $ chef prepare page about
    Creating page: pages/about.md

Edit that file and change it to something more appropriate... make the title
something like "_About This Site_", and add some text.

You should still have the server running, so type
`http://localhost:8080/about.html` in the address bar. You should see your new
page show up.

Of course, you probably want a link to that page -- it's not very useful if
visitors have to know the URL in order to reach it. We could go into layout
and templating considerations so that we can add it in some kind of sidebar
menu, but we'll keep this tutorial short for now. Instead, let's just add a link
to it from one of your blog posts.

Open your last created post in a text file, and add something like this:

    {%raw%}
    You can learn more [about this site here]({{pcurl('about')}})
    {%endraw%}

Go back to the home page (`http://localhost:8080`) in your browser and look for
that new piece of text. It should feature a hyperlink to your new "_About_"
page.

Here's how this worked:

* The `[text here](url)` syntax is [Markdown][mdown] for hyperlink. All the
  posts and pages files have a `.md` extension, which means PieCrust will use
  Markdown to format it. This means you can use things like `*asterisks*` and
  `**double asterisks**` to show *italics* and **bold** things. See any
  [Markdown cheat sheet][mdown] to learn about this simple syntax.

* As mentioned above, the part in parenthesis is supposed to be the URL of the
  hyperlink, so you might be wondering why we're writing this weird
  {%raw%}`{{pcurl('about')}}`{%endraw%} thing instead of just something like
  `/about.html`.

    The reason is that a fixed URL is easy to break -- when you change the root
    URL of your site, or when you change between "ugly" URLs (with the `.html`
    extension) and "pretty" URLs (without the extension), along with a few other
    possible changes.

    The `pcurl` function generates the URL according to the current situation
    and is therefore much more versatile. You can read [more on routing and
    URL functions][routes], or [more on templating in general][tpl].


## Configuring the website

This is all fine and dandy, but the big title at the top of the home page still
says "_My New Website_", and that's not very personal. Let's configure that.

Open the `config.yml` file. It's also written in [YAML][], like the posts'
configuration headers. You can change the `site/title` setting easily:

    site:
        title: "Ludovic's Blog"

> Note how, for the rest of this tutorial (and the rest of the documentation!)
> we'll refer to nested configuration settings using *slash* separators. So the
> `site/title` setting refers to the `title` setting inside the `site` setting,
> as shown in the snippet above.

Refresh your browser, and lo and behold, the new title should be there.

There are plenty of other things you can configure in the `config.yml` file. For
example, say you don't like the default URL format for posts. That can be
adjusted with the `site/post_url` setting. By default, it is:

    site:
        post_url: "%year%/%month%/%day%/%slug%"

The post URL format is defined using some keywords surrounded by percent signs,
as you can see above. The `%year%`, `%month%` and `%day%` keywords should be
self-explanatory -- and they map directly to the post's filename, which, if you
remember, contains the post's date.

The `%slug%` keyword maps to the post's "*slug*", which is the [part of the URL
that has human-readable words][slug]. In PieCrust's case, it comes from the
part of the filename that comes after the date ("*my-first-post* and
*my-second-post* in this tutorial).

If, say, your blog has a low chance of slug collision, or has a low post
frequency, and you want to have more minimal URLs, you can change it to:

    site:
        post_url: "%year%/%slug%"

Refresh your browser, and you should see that the posts' URLs are now conforming
to the new format.

> If your browser was currently displaying a post at the old URL, you will
> suddenly get a "_page not found_" error! That's OK, it's because the post is
> now at the new, shorter URL. Just go back to the root URL, `localhost:8080`.

See the [site configuration reference][siteconfref] for more information about
all the settings you can change.


## Next steps

At this point you have a moderately function blog, but it's far from looking
good yet. In the [second part of this tutorial][part2] we'll look at customizing
your website's appearance by editing layouts and templates, and writing CSS
stylesheets and using PieCrust's built-in asset pipeline.



[1]: {{pcurl('getting-started')}}
[2]: {{piecrust.url}}
[yaml]: https://en.wikipedia.org/wiki/YAML
[slug]: http://en.wikipedia.org/wiki/Semantic_URL#Slug
[pageconfref]: {{pcurl('docs/reference/page-config')}}
[siteconfref]: {{pcurl('docs/reference/website-config')}}
[part2]: {{pcurl('docs/tutorial/making-things-pretty')}}
[routes]: {{docurl('content-model/routes')}}
[tpl]: {{docurl('content/templating')}}
[mdown]: http://commonmark.org/help/

