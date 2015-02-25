---
title: "Appendix 2: Page Configuration Reference"
short_title: Page Configuration
---

This is a list of the settings handled by PieCrust in a page's configuration
header.

* `blog`: Alias of the `source` setting, to make it easier to remember when
  using the default content model.

* `cache_time`: Specifies the value for the `Cache-Time` HTTP header when this
  page is served in CMS mode.

* `category`: Specifies the optional category that the page is part of. This is
  not strictly speaking used by PieCrust itself, but is used by the default
  content model.

* `content_type`: Specifies the value for the `Content-Type` HTTP header when
  this page is served in CMS mode.

* `date`: Sets the date of the page. Note that some sources, like the blog posts
  sources, already set the date using the page's filename.

* `format`: Specifies what formatter to use to render this page. Defaults to
  `site/default_format`, which defaults to Markdown.

* `items_per_page`: Defines how many items to include per page when using the
  `pagination` data endpoint.

* `layout`: Specifies what layout to use to render this page. Defaults to
  `default`.

* `posts_per_page`: Alias of the `items_per_page` setting.

* `source`: Defines what page source to use with the `pagination` data endpoint.

* `tags`: An array of strings that represents labels the page is part of. This
  is not strictly speaking used by PieCrust itself, but is used by the default
  content model.

* `template_engine`: Specifies the template engine to use to render this page.
  Defaults to `site/default_template_engine`, which defaults to Jinja2.

* `title`: Defines the title of the page. This is not strictly speaking used by
  PieCrust itself, but is used by the default theme.

* `time`: Sets the time of the page. This can be used to complement the `date`
  setting, whether it was set through the configuration header, or by the
  source.

