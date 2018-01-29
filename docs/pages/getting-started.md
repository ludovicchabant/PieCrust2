---
title: Getting Started
header_class: pc-tutorial
nav_key: tutorial
---

This quick tutorial will show you how to create a simple blog with PieCrust.

> If you're already an experienced cook, here's the rundown:
>
>     virtualenv pcenv
>     <activate pcenv>
>     pip install piecrust --pre
>     chef init mywebsite
>     cd mywebsite
>     chef prepare post my-first-post
>     chef serve
>     chef bake


## Installation

The first step is obviously to get PieCrust installed on your machine.

You'll need Python 3.4 at least for this. Note that it can live side by side
with Python 2.x. On Windows or MacOSX, you can use the [official Python
installer][1]. On main Linux distros, you can use your system's package manager
to install it. If you're on a more obscure system, or if you want to use
alternative means like Homebrew or something, you probably don't need help for
this!

Now we can start running in a command line. On MacOSX, that's the Terminal app,
and on Windows that's the Command Prompt.


### Global installation

Python 3 comes with a [package manager][2] called `pip`, with which you can install,
update, and uninstall Python programs like PieCrust. Just run:

    pip install piecrust --pre

This will install PieCrust globally on your system. You may want to install it
using a *virtual environment* instead, though. See the next section for that.

> #### Permission Errors
>
> If you get some permission errors, you may have to run that command as an
> administrator. That would be `sudo pip install piecrust --pre` on MacOSX and
> Linux, or running the Command Prompt as an Administrator on Windows.

You should now have PieCrust installed! You can check that it works by typing:

    chef --version

If everything's fine it should print `{{piecrust.version}}` (the latest
version as of this writing).


### Using virtual environements

Although very straightforward, the previous section installs PieCrust globally
on your system. This may be OK, but could also cause problems if you have other
Python software that share dependencies with PieCrust, but with different
versions.  And then there's the issue of installing PieCrust in environments in
which you don't have administrator access.

Thankfully, `pip` supports a whole variety of scenarios, and [another
utility][3], called `virtualenv` enables even more of them.

* If you don't have it yet, install `virtualenv` with `pip install virtualenv`,
  or check with your administrators to have it. Most web hosts provide it.
* Run `virtualenv pcenv`. This will create a directory called `pcenv` that
  contains a whole new Python environment, separate from your system's Python
  environment.
* Activate that environment with `sh pcenv/bin/activate.sh` (on Linux or MacOSX)
  or `pcenv\Scripts\activate` (on Windows). The new environment will now be
  active for as long as your current command prompt is active.
* Now install PieCrust with `pip install piecrust --pre`. This will install it
  in that environment, leaving your system's Python clean of any of PieCrust's
  dependencies.


## Create an empty website

The `chef` command is the main PieCrust utility. You can read about it on the
[command-line overview][cmdline] page. The first thing to do is to ask it to
create a basic website structure:

    chef init mywebsite

This should create a directory called `mywebsite`. There should be a
`config.yml` file in there. Get into that directory:

    cd mywebsite

Once you're inside a website's root directory, the `chef` command will be able
to do a lot of different things.


## Create new content

Let's start by creating a new page:

    chef prepare page about-me

It will tell you that it just created a file named `pages/about-me.md`. Go ahead
and edit that in your favorite text editor, and write some text, or change the
title that was defined for you in the header part. For more information on
writing content, see the documentation about [creating pages][cnt].

Now let's write a blog post:

    chef prepare post my-new-blog

It will again tell you about the file it just created. This time it's in the
`posts` folder, and has a name that follows some date/title kind of naming
convention. You don't have to use `chef prepare` to create content for your
website, but for things like blog posts it's a lot easier to let it insert
today's date in the filename.


## Preview content

Time to preview what we just did! Simply type:

    chef serve

Open your favorite web browser and navigate to the URL that `chef` is listening
on, which by default is `localhost:8080`. You should see some placeholder text
along with today's blog post that you just created, with a simple barebones theme.

> #### Alternate port
>
> If you already have some other things running on port 8080, you can tell
> PieCrust to use a different one with the `-p` option.

The `about-me` page isn't shown because you're looking at the index page, but
you would see it if you navigated to `localhost:8080/about-me`.


## Bake and publish

Now it's time to bake this new site and publish it somewhere. There are many
ways to do that, as shown in the documentation about [baking][bake], but here's
a quick way. Run:

    chef bake

This will bake the website into static files, stored under the `_counter`
directory. At this point, you can upload all the contents of that directory to
your web server. When that's done, you should be able to see the exact same
website being served from there.


That's it! This is an extremely quick tour of PieCrust. Read the [documentation][doc] to learn more.


[1]: https://www.python.org/downloads/
[2]: https://pip.pypa.io/en/latest/
[3]: https://virtualenv.pypa.io/en/latest/
[doc]: {{pcurl('docs')}}
[cmdline]: {{pcurl('docs/general/command-line-overview')}}
[cnt]: {{pcurl('docs/content/creating-pages')}}
[bake]: {{pcurl('docs/publish')}}

