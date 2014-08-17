
PieCrust is a static website generator and lightweight CMS that's all managed
with text files. No complex setup, databases, or administrative panels.
Simple, beautiful, and yummy.

For more information, along with the complete documentation, visit `the
official website`_.

.. _the official website: http://bolt80.com/piecrust/


Quickstart
==========

If you want to quickly give it a spin:

::

    bin/chef init mywebsite
    cd mywebsite
    ../bin/chef serve

It should create a new empty site in a ``mywebsite`` folder, and then start
your default browser to show it to you. Use ``chef prepare page`` and ``chef
prepare post`` to create pages and posts, and edit those in your favorite text
editor.

When you're happy, run ``../bin/chef bake`` to generate the final static
website, which you'll find in ``_counter``.


Changes
=======

Check out the CHANGELOG file for new features, bug fixes and breaking changes. 

