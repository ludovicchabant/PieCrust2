

From the package server
-----------------------

The simplest way to install PieCrust is to install it from PyPi_, the Python
package index:

::

    easy_install piecrust

or:

::

    pip install piecrust

You'll need to have Python3 installed (support for Python2 may come later).

.. _Pypi: https://pypi.python.org/pypi


From a tarball
--------------

You can also install PieCrust using a snapshot of the code. See the `download
page`_ where you can either get the `very latest`_, or any of the previous
official releases. Then you can point ``pip`` to the tarball (either one you
previously downloaded, or directly from BitBucket):

::

    pip install https://bitbucket.org/ludovicchabant/piecrust2/get/tip.tar.gz

You'll need to have Python3 installed (support for Python2 may come later).

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

You'll also need to have Python3 installed (support for Python2 may come later).

On Mac/Linux:

::

    virtualenv -p python3 venv
    . venv/bin/activate
    pip install piecrust

On Windows:

::

    virtualenv -p python3 venv
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


From source
-----------

If you intend to stay close to the development branch of PieCrust, or if you
want to contribute to the project with some coding of you own, you may want to
clone the repository locally and run PieCrust from there.

In order to install PieCrust's dependencies, it's recommended to use a virtual
environment (see above). If you're familiar with Python development, you should
know all about this already. Also, so far, PieCrust is a Python3-only project
(support for Python2 may come later) so make sure you have that installed.

Using Mercurial:

::

    hg clone https://bitbucket.org/ludovicchabant/piecrust2

Using Git:

::

    git clone https://github.com/ludovicchabant/PieCrust2.git


Then create the virtual environment and install dependencies.

On Mac/Linux:

::

    cd <your clone of PieCrust2>
    virtualenv -p pyton3 venv
    . venv/bin/activate
    pip install -r requirements.txt

On Windows:

::

    cd <your clone of PieCrust2>
    virtualenv -p python3 venv
    venv\Scripts\activate
    pip install -r requirements.txt

To run PieCrust, run ``bin/chef`` (on Mac/Linux) or ``bin\chef.cmd`` (on
Windows), which is basically the same as running ``python chef.py``. Make sure
that you're running this with the virtual environment active.

When you want to update PieCrust, do ``hg pull -u`` or ``git pull``, depending
on which source control system you used to clone the repository, and then
update any dependencies that may have changed:

::

    pip install -r requirements.txt -U

