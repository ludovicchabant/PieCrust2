---
title: How It Works
---

PieCrust websites are highly customizable, but they rely on a few simple
principles that you can learn in a minute.


## Content sources

A PieCrust website is made of _content sources_, which are what tells PieCrust
where to find content, and how to read it. 

In most cases, a content source will read content from more-or-less organized
files on disk. Sometimes, that content will be media files (images and
animations), or some kind of code (Javascript or CSS related), but most of the
time this will be the text you want to publish. As a result, in this
documentation, we mostly talk about "page sources" as opposed to the more
generic "content sources".

You can read more on [content sources here][src].


## Content pipelines

Once PieCrust knows about your content, it needs to be able to bake it into
static files, or to serve it to a browser. That's what _content pipelines_ are
for: they know how to process raw source content, and convert it into whatever
the output format is supposed to be.

In some cases, the output format is a web-related format like HTML, RSS/Atom,
Javascript, or CSS. In other cases, it might be JPEG, PDF, or anything, really.

You can read more on [content pipelines here][ppl], especially the two main
pipelines in PieCrust, the page and asset pipelines.


[src]: {{docurl('content-model/sources')}}
[ppl]: {{docurl('content-model/pipelines')}}
