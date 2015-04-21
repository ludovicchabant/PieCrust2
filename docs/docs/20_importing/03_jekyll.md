---
title: Importing from Jekyll
---

You can import your website from Jekyll by running:

    chef import jekyll /path/to/jekyll/website

This will import the whole website -- pages, posts, templates, etc. It will
attempt to convert Liquid templates to Jinja, but may fail if you're using
advanced syntax tricks or custom tags and filters.

