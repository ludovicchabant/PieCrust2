---
title: Importing from Wordpress
---

If you have a Wordpress site already, you can [export an XML archive][1] very
easily. Go into the administration panel and choose "_Tools > Export_". Keep the
"_All content_" option selected, and hit the "_Download export file_" button.

Now create a new PieCrust website and import that archive:

    chef init myblog
    cd myblog
    chef import wordpress-xml /path/to/archive.xml

This will create all the pages, posts, and metadata in the current PieCrust
website.

Be aware of the following caveats however:

* The import process will edit the current website's configuration file to set
  some properties on it, like the website's title and list of authors.

* At the moment, only _content_ is imported, not themes and templates and such.
  Although it may be technically possible to do so, many Wordpress themes come
  with commercial licenses which could potentially prevent converting it.

* Because Wordpress stores its pages' contents in raw HTML, you won't get nice
  Markdown or Textile syntax from the import process.

* PieCrust will import any attachments to pages or posts (images, etc.). This
  means it will make requests to the original URLs of those attachments in order
  to download them. If your Wordpress website was taken down, PieCrust won't be
  able to download anything and you'll be missing things from the imported
  website.

* If you had comments in your Wordpress blog, they will be lost. You can however
  import those comments in a service like Disqus, and then use Disqus on your
  PieCrust website.


[1]: https://en.support.wordpress.com/export/

