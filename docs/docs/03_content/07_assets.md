---
title: Assets
---

Writing text is all good, but sometimes you need to add some pictures in your
pages. You could easily handle this yourself by having an images folder at the
root of your website with all your pictures in it:

    ![my picture](/images/path/to/my/picture.png)

However, your images folder could easily get cluttered and difficult to
organize, especially if you use pictures a lot in your blog posts. And it's not
super friendly to write.

To solve some of these problems, PieCrust has a "_page assets_" mechanism for
any kind of file you want to somehow be related to a page (pictures, audio
files, etc.).

You put all the assets for a page in a sub-directory that has the same name as
the page file, with a `-assets` suffix. For instance, if you have a page at
`pages/about/where-to-find-us.md`, you can create a
`pages/about/where-to-find-us-assets` directory with stuff in it:

    pages
     |- about
         |- where-to-find-us.html
         |- where-to-find-us-assets
             |- map.jpg
             |- street-view.jpg

Then, on the page, you can access those assets with the assets variable and the
name of the asset (without the extension):

    {%raw%}
    ![map to our place]({{ assets.map }})
    ![our place]({{ assets['street-view'] }})
    {%endraw%}

You can also loop over a page's assets:

    {%raw%}
    {% for a in assets %}
    <img src="{{a}}" alt="" />
    {% endfor %}
    {%endraw%}

