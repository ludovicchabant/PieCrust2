---
title: Plugins
---

To create a PieCrust plugin, you need to do a few things:

* Create a correct `setuptools` package.
* Implement a sub-class of `PieCrustPlugin`.
* Write a couple lines of boilerplate code.


## Packaging plugins

PieCrust plugins are expected to be available on [Pypi][] for better integration
with `chef` commands. For instance, the `chef plugins list -a` will list all
PieCrust plugins from Pypi.

A PieCrust plugin package must:

* Be named `PieCrust-FooBar`, where `FooBar` is the name of the plugin.
* Have a module named `piecrust_foobar`, which is basically the lower-case
  version of the package name, with an underscore instead of a dash.

You can refer to the [`setuptools` documentation][st] for more information.


## The plugin class

A PieCrust plugin is an instance of a class that derives from `PieCrustPlugin`.
The only required thing you need to override is the name of the plugin:

    from piecrust.plugins.base import PieCrustPlugin

    class FooBarPlugin(PieCrustPlugin):
        name = 'FooBar'

The plugin class has a whole bunch of functions returning whatever your plugin
may want to extend: formatters, template engines, `chef` commands, sources, etc.
Each one of those returns an array of instances or classes, depending on the
situation.

Check the `piecrust.plugins.builtin.BuiltInPlugin` to see how all PieCrust
functionality is implemented.


## Boilerplate code

Now we have a plugin class, and a Pypi package that PieCrust can find if needed.
All we need is a way to tell PieCrust how to find your plugin class in that
package.

In the required `piecrust_foobar` module, you need to define a
`__piecrust_plugin__` global variable that points to your plugin class:

    __piecrust_plugin__ = FooBarPlugin

That's what PieCrust will use to instantiate your plugin.


## Loading the plugin

Now you can add your plugin to a PieCrust website by adding this to the website
configuration:

    site:
        plugins: foobar

PieCrust will prepend `piecrust_` to each specified plugin name and attempt to
load that as a module (`import piecrust_foobar`). If this succeeds, it will look
for a `__piecrust_plugin__` in that module, and expect its value to be a class
that inherits from `PieCrustPlugin`. If everything's OK, it will instantiate
that class and query it for various services and components when necessary.


[pypi]: https://pypi.python.org/pypi
[st]: http://pythonhosted.org/setuptools/

