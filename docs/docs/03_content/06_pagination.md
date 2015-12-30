---
title: Pagination
---

There are typically a few pages that need to display a list of articles, like
the main page of a blog. To do this in PieCrust, you can use the `pagination`
variable on a page:

    {% raw %}
    {% for post in pagination.posts %}
    ## [{{ post.title }}]({{ post.url }})
    <span class="post-date">{{ post.date }}</span>
    {{ post.content|safe }}
    {% endfor %}
    {% endraw %}

This will display a list of posts, each with its title (note the level 2
Markdown title syntax) as a link, its date, and its content.

For more information on what's available on the `pagination` object, see the
[templating data reference page][tpldata]. Also see the [templating
documentation][tpl] for more general information about template engines in
PieCrust.

Note that the pagination variable is called like that because it will paginate
the current page by creating sub-pages (see below). If you want to display pages
with a list of posts without any pagination (i.e. without any sub-page), you can
instead use the `blog.posts` template variable (see the documentation about the
[default content model][dcm] for more information about that).


## Pagination filtering

If you want to create a page that lists only specific posts, you can filter what
you get from the pagination object. You do this with the `posts_filters`
configuration section in your page.

For example:

    posts_filters:
      has_tags: announcement
      has_tags: piecrust

This will only return posts with both the `announcement` and `piecrust` tags.

See the documentation on the [page filtering syntax][fil] for more information.


## Sub-pages

Most pages don’t have sub-pages — there’s just the page. However, pages that
show a list of blog posts (or other lists involving pagination) could have
sub-pages if there are too many blog posts.

For example, if you only show 5 posts per page and you have written 17 posts in
total, your blog’s main page would have 4 sub-pages: sub-page 1 would show posts
17 to 13, sub-page 2 would show posts 12 to 7, etc. (posts are sorted in
reverse-chronological order by default, but other things may be sorted
differently).

If a page’s URL is domain.com/blog, its 3rd sub-page’s URL would look like
domain.com/blog/3. This means it’s a bad idea to create an actual page whose
name is just a number!


[tpl]: {{docurl('content/templating')}}
[tpldata]: {{docurl('reference/templating-data')}}
[dcm]: {{docurl('content-model/default-model')}}
[fil]: {{docurl('content/filtering')}}

