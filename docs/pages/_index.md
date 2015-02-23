---
title: PieCrust
layout: splash
---

---slogan---

Baking fresh websites & documents since 2006


---main---

**PieCrust** is a static website generator and flat-file CMS. No complex setup,
databases, or administrative panels -- it's all text files. Simple, beautiful,
and yummy.

*[CMS]: Content Management System


---simple---

### Store in the cellar

Because all your site's content and configuration is stored in simple text
files, it fits nicely in a revision control system like Git or Mercurial. It's
not only more practical, but also safer!


---bake---

### Serve on the counter

Although it can run a flat-file CMS, **PieCrust** is designed as a static
website generator. This means it can "bake" your website into simple HTML files
that you can publish with a minimum of resources on your server. A sudden spike
of visitors can't crash your MySQL database when you don't need one!


---ingr---

### Familiar ingredients

**PieCrust** uses all the ingredients you already like, such as Markdown and
Textile for formatting, or Jinja2 and Mustache for templating.


---oven---

### Fully functioning oven

**PieCrust** comes out-of-the-box with an asset processing pipeline, capable of
handling most of your files -- Less/Sass processing, CSS and JS
minification, concatenation, and more.


---cooks---

### Several cooks in the kitchen

If you're dealing with advanced scenarios, **PieCrust** will gladly interoperate
with other tools like Grunt, Compass, Bower, and many more.


---fast---

### Super-fast service

Because **PieCrust** is also designed as a lightweight (flat-file) CMS, it can
render your pages in less than a few milliseconds in most cases. It means that
previewing or generating your website is super fast!


---carte---

### A La Carte Content

**PieCrust** comes with a powerful system of page sources, routes, and taxonomies.
This means you can completely customize how you want to author your content, and
how it gets exposed.


---entrees---

### Multiple entrées

Your pages are not limited to one piece of content that you place in the center
of your layout. You can define other “text segments” like a page-specific menu
or sidebar text that you can insert in different places in the layout.


---startnow---

## Get Started Now

You can follow the detailed instructions on the [Getting Started][1]
page, or, if you're already experienced in the culinary arts:

    virtualenv pcenv
    <activate pcenv>
    pip install piecrust
    chef init mynewwebsite
    cd mynewwebsite
    chef prepare post my-first-post
    chef serve
    chef bake


 [1]: {{pcurl('getting-started')}}

