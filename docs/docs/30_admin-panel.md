---
title: Administration Panel
short_title: Admin Panel
---

Remember when we said there was no complex administration panel? Well, we kinda
lied. Only not really, since the one that comes with PieCrust is super simple
and, of course, completely optional. That's why we're only bringing it up here.

![Administration Panel]({{assets.dashboard}})

To run the administration panel, type:

```
chef serve --admin
```

Now browse to the admin URL (`http://localhost:8080/pc-admin`) with your
favorite browser and you should see "FoodTruck", PieCrust's administrative
panel.

* [Using the administration panel][using]: explains how the administration panel
  works, and how you can improve its handling of you website with a few settings
  in your site's configuration.

* [Deploying the administration panel][deploy]: gives a few tips for making the
  administration panel available on your production server.

[using]: {{docurl('admin-panel/using-the-panel')}}
[deploy]: {{docurl('admin-panel/deploying-the-panel')}}
