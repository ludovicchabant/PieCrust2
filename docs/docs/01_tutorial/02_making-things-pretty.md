---
title: "Part 2: Making Things Pretty"
---

In the [first part of this tutorial][part1], we created a very simple blog with
an "_About_" page and a couple of posts. But it has a very barebones look, and
we want some custom navigation links, along with a few more custom pages.


## Changing the layout

### Overriding the default theme

If you looked at the files in your website's directory, you'll see there's only
your content. The layout and CSS styles come from the _default PieCrust theme_,
which ships with PieCrust's code (in `piecrust/resources/theme`).

What we can do, with a simple command, is copy all of the default theme's files
into our website, for easy customization:

    $ chef themes override
    pages/_category.html
    pages/_index.html
    pages/_tag.html
    templates/default.html
    templates/partial_post.html
    templates/post.html

All of those files have been copied into your website's directory -- and it will
warn you if it was every going to overwrite some of your own files.

There are a few files we'll be editing here:

* `pages/_index.html`: That's the main page.
* `templates/default.html`: That's the default layout for all the pages
  (including `_index.html` and `about.html`, which we created in part 1 of this
  tutorial).
* `templates/post.html`: That's the default layout for a blog post.


### Rewriting the main page

Let's start with the `pages/_index.html` page. You'll see a _lot_ of stuff in
there. Don't worry, that's just the default welcome text for when you create an
empty website and you preview it right away.

Let's just keep the top section -- which loops over the latest blog posts and
displays them -- and delete everything after (and including) `<--markdown-->`.

For this blog, however, maybe we want something different for the home page. How
about we only show a list of dates and titles? Let's rewrite the part we kept.

First, we don't need to write stuff in raw HTML at this point so remove the
`format: none` from the configuration header (at the top of the file). This will
revert the page back to the default Markdown formatter.

Second, change the code to:

    {% raw %}
    {% for post in pagination.posts %}
    * {{post.date}} **[{{post.title}}]({{post.url}})**
    {% endfor %}

    <section>
        {% if pagination.prev_page %}<div class="prev"><a href="{{ pagination.prev_page }}">Next Posts</a></div>{% endif %}
        {% if pagination.next_page %}<div class="next"><a href="{{ pagination.next_page }}">Previous Posts</a></div>{% endif %}
    </section>
    {% endraw %}

We're still showing links to the previous/next pagination at the bootom, but now
instead of showing a classic river of posts, we're showing a concise and simple
list.

> Note how the `for` loop generates several lines starting with a star, which
> gets formatted by Markdown into an HTML list. Also see how we create links
> with the usual Markdown syntax, but we pass it the title and URL of each post
> being looped upon by using Jinja syntax.

Now that we refresh the browser, the home page looks very clean and simple...
maybe too clean and simple though. Visitors may want a little hint as to what
each blog post talks about, especially if you're the kind of blogger to give
cryptic or funny titles to your posts. This is a good way to show how defining
and using metadata on your content is super easy in PieCrust.

Let's change the loop to:

    {% raw %}
    {% for post in pagination.posts %}
    * {{post.date}} **[{{post.title}}]({{post.url}})**{%if post.hint%}: {{post.hint}}{%endif%}
    {% endfor %}
    {% endraw %}

This will show a post's `hint` if it is defined. Of course, if you refresh the
page now, nothing will change.

Now go into some of your posts, and add something like this to their
configuration header:

    ---
    <existing configuration settings...>
    hint: Where we announce things
    ---

Refresh the home page, and you'll see this new piece of metadata displayed next
to the post's title!

> Using page metadata in PieCrust is both easy and powerful, because you
> can sort, filter, display, and more, based on those metadata values.


### Changing the default layout

Because the main page doesn't specify any custom layout, it will use the default
layout which is located at `templates/default.html`. If you open that file,
you'll realize that it's where the default PieCrust theme does all the stuff you
see it doing: setting the page title, defining some simple CSS theme, etc.

In order not to get lost in HTML/CSS considerations, instead of just looking at
how PieCrust works, let's do a simple edit. We'll add a link to the "_About_"
page we created in the first part of this tutorial in the footer part of every
page.

Edit `templates/default.html` and replace the last line of the footer
(_i.e._ just before `</footer>`) with this:

    <p><a href="{{pcurl('about')}}">About this site</a> &ndash; {{ piecrust.branding|safe }}</p>

Refresh your browser, and you should see a link to the "_About_" page at the
bottom of every page, including blog posts.

> Blog posts use the `post` layout by default (which you can find at
> `templates/post.hml`) instead of `default`. But in the case of PieCrust's
> default theme, which we override here, it's the same layout. Indeed, if you
> open the `post` layout, you'll see it only has one line which says that it
> extends the `default` layout.

You'll probably spend lots of time in here, tweaking your navigation sidebars
and your margins and whatnot. Besides fighting CSS and browser inconsistencies,
you'll also probably refer a lot to the [Jinja templating documentation][jinja]
for your template logic, unless you end up using [another template engine][tpl].

## Next steps

In the [third part of this tutorial][part3], we'll look at PieCrust's built-in
asset pipeline, by writing some CSS code.


[part1]: {{docurl('tutorial/your-first-blog')}}
[part3]: {{docurl('tutorial/adding-colours')}}
[tpl]: {{docurl('content/templating')}}
[jinja]: http://jinja.pocoo.org/docs/dev/templates/

