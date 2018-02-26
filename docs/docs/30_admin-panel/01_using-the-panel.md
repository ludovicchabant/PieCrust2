---
title: Using the Administration Panel
---

The navigation menu on the left should have:

* The dashboard.
* One entry for each of your page sources.
* An interface to publish your website.

## The Dashboard

This is where you can see a summary of your website, with links to see your list
of already existing content.

If your website content is also stored in a version control system, you can see
what's currently edited in the "_Work in Progress_" section.

> Right now, FoodTruck only supports Mercurial for source control.


## Page Sources

For each source, you can list the existing pages:

![Page Sources]({{assets.listsrc}})

Clicking on any link will let you edit that page.

You can also create a new page by clicking the appropriate entry in the left
navigation menu. You'll have to fill up information similar to what you specify
to the `chef prepare` command:

![New Page]({{assets.writenew}})

Once you created a page, or click a link for an existing one, you can edit the
page:

![Edit Page]({{assets.edit}})

Note that if your website is stored in a VCS, you'll have the ability to commit
the page file if you want, but using the dropdown on the "_Save_" button:

![Commit Page]({{assets.commit}})


## Publishing

You also have a UI for running your [publish targets][pub]. The descriptions shown for
each target are taken from a `description` entry in their configuration
settings.

![Publish]({{assets.publish}})

Clicking any "_Execute_" button will publish your website using the
corresponding target. You'll see some notifications popup on the bottom right to
indicate the progress of the operation.


[pub]: {{docurl("publishing")}}

