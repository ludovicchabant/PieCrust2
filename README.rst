
PieCrust is a static website generator and lightweight CMS that's all managed
with text files. No complex setup, databases, or administrative panels.
Simple, beautiful, and yummy.

For more information, along with the complete documentation, visit `the
official website`_.

.. _the official website: http://bolt80.com/piecrust/


|pypi-version| |pypi-downloads| |build-status|

.. |pypi-version| image:: https://img.shields.io/pypi/v/piecrust.svg
   :target: https://pypi.python.org/pypi/piecrust
   :alt: PyPI: the Python Package Index
.. |pypi-downloads| image:: https://img.shields.io/pypi/dm/piecrust.svg
   :target: https://pypi.python.org/pypi/piecrust
   :alt: PyPI: the Python Package Index
.. |build-status| image:: https://img.shields.io/travis/ludovicchabant/PieCrust2/master.svg
   :target: https://travis-ci.org/ludovicchabant/PieCrust2
   :alt: Travis CI: continuous integration status



Quickstart
==========

If you want to quickly give it a spin:

::

    pip install piecrust
    chef init mywebsite
    cd mywebsite
    chef serve

It should create a new empty site in a ``mywebsite`` folder, and start a small
web server to preview it. You can then point your browser to ``localhost:8080``
to see the default home page.

Use ``chef prepare page`` and ``chef prepare post`` to create pages and posts,
and edit those in your favorite text editor.

When you're happy, run ``chef bake`` to generate the final static website,
which you'll find in ``_counter``. At this point you can upload the contents of
``_counter`` to your server.


Changes
=======

Check out the ``CHANGELOG`` file for new features, bug fixes and breaking
changes. You can `see it online here <https://bitbucket.org/ludovicchabant/piecrust2/raw/default/CHANGELOG.rst>`__.


Installation
============

You can install PieCrust like any other package:

::

    pip install piecrust

For more options to get PieCrust on your machine, see the ``INSTALL`` file. You
can `see it online here <https://bitbucket.org/ludovicchabant/piecrust2/raw/default/INSTALL.rst>`__.

