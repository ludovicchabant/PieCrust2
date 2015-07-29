---
title: Page Sources
---

A page source is a component that retrieves pages from _somewhere_, and gives
them to the rest of the application for processing. A typical blog would have 2
sources: one for the blog posts, and one for the other pages (like the main
page, an "_about_" page, some archives, etc.).

To provide new page sources, you need to override the `getSources` method of
your plugin, and return source _types_ (not instances!).


```python
class MyPlugin(PieCrustPlugin):
    name = 'myplugin'

    def getSources(self):
        return [
                MyCustomSource]
```


## Basic Implementation

To implement a page source, you need to inherit from the `PageSource` class:

```python
from piecrust.sources.base import PageSource

class MyCustomSource(PageSource):
    def __init__(self, app, name, config):
        super(MyCustomSource, self).__init__(app, name, config)
        # Other stuff...

```

There are 3 methods you need to override for a basic, functioning page source.

* `buildPageFactories(self)`: you should be returning a list of `PageFactory`
  objects here -- one for each page inside the given source. Your source
  instance has access to its configuration settings from the website's
  `config.yml`, and to the current `PieCrust` application, among other things.
  A `PageFactory` object describes how a page should be created. It has a
  `ref_path` (_i.e._ a source-specific path which, for a simple source, could
  just be the relative path of the page file inside the source's directory), and
  some `metadata`. See "_Source Metadata_" later on this page.

* `resolveRef(self, ref_path)`: you should return a tuple that describes the
  page found at `ref_path`. The tuple contains the full path of the page file,
  and the _source metadata_ for it.

* `findPageFactory(self, metadata, mode)`: this is mostly useful when running
  PieCrust as a dynamic CMS (which incidentally is also the case when previewing
  with `chef serve`). Based on the _route metadata_ provided, the source is
  expected to do its best to find a matching page, and return a `PageFactory`
  for it.

  The `mode` can either be `MODE_PARSING` or `MODE_CREATING`. The first mode
  expects you to return a `PageFactory` for an existing page. That's the mode
  that will always be given while running `chef serve`. The second mode expects
  you to return a factory for a _non-existing_ page. That's the mode that will
  be given when running `chef prepare`, _i.e._ when the application wants to
  create a new page for a source, and needs to know exactly what file to create.


## Source Metadata



## Mixins


