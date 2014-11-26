
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

Check out the ``CHANGELOG`` file for new features, bug fixes and breaking changes. 


Installation
============

From the package server
-----------------------

The simplest way to install PieCrust is to install it from PyPi_, the Python
package index:

::

    easy_install piecrust

or:

::

    pip install piecrust

.. _Pypi: https://pypi.python.org/pypi


From a tarball
--------------

You can also install PieCrust using a snapshot of the code. See the `download
page`_ where you can either get the `very latest`_, or any of the previous
official releases. Then you can point ``pip`` to the tarball (either one you
previously downloaded, or directly from BitBucket):

::

    pip install https://bitbucket.org/ludovicchabant/piecrust2/get/tip.tar.gz


.. _download page: https://bitbucket.org/ludovicchabant/piecrust2/downloads
.. _very latest: https://bitbucket.org/ludovicchabant/piecrust2/get/tip.tar.gz


Using a virtual environment
---------------------------

This method is not as simple as the previous ones, but is probably the
recommended one. All the methods so far will install PieCrust globally on your
system, which is fine if you're installing it on your own computer, but may
cause problems later. For instance, PieCrust may have some dependencies in
common with some other Python programs you have installed, and things may break
when you update one of them. Alternatively, you may just want to install
PieCrust on a computer you don't fully control, like in a shared hosting
environment. Or maybe you just like things to be tidy.

For this you'll need ``virtualenv``. A virtual environment is simply a folder
on your computer that contains a portable, fully functional Python environment
-- one that would, in this case, contain a certain version of PieCrust, along
with all its dependencies, separate from your global Python installation.

On Mac/Linux:

::

    virtualenv venv
    . venv/bin/activate
    pip install piecrust

On Windows:

::

    virtualenv venv
    venv\Scripts\activate
    pip install piecrust


If the first command fails, chances are that you don't have ``virtualenv``
installed. You should be able to install it with:

::

    pip install virtualenv

Some Linux/UNIX-based systems have it in their package manager, so if that
doesn't work you can try:

::

    apt-get install virtualenv

If both fail, you may have to get it "by hand", by `downloading the code from
PyPi`_, extracting the archive, and running it from there. For instance, on
Linux/UNIX:

::

    wget http://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.11.6.tar.gz
    tar xzf virtualenv-1.11.6.tar.gz
    python virtualenv-1.11.6/virtualenv.py venv

From there, you can continue with activating the virtual environment and
install PieCrust in it, as shown previously.


.. _downloading the code from PyPi: https://pypi.python.org/pypi/virtualenv#downloads

