---
title: Chef
---

Running commands is done through the `chef` program. You can type `chef --help`
and get the complete list of commands and options.

## Commands

The most common commands are:

* `init`: This is the command that creates a new website. All it does really is
  create a new directory with a `config.yml` file in it. For more information,
  see the [Website Structure][1] page.

* `prepare`: Creating and editing text files is easy enough, but it can be even
  easier if you have a command to name the file for you -- especially for blog
  posts which often require today's date in their name. The `prepare` command
  can create a variety of content, but `prepare page` and `prepare post` are the
  most common usage. More more information, see [Creating Pages][2].

* `serve`: Previewing your website locally as you work on it is made possible by
  PieCrust's built-in web server. After running the `serve` command, your
  website will be reachable at `http://localhost:8080`. Hitting `<F5>` to
  refresh the page is all you need to see updated content as you edit it.

* `bake`: Finally, the `bake` command transforms all your content -- pages,
  templates, layouts, assets -- into a self-contained static website that you
  can upload to your public server.

[1]: {{docurl('general/creating-websites')}}
[2]: {{docurl('content/creating-pages')}}


## Global options

The `chef` accepts various global options that can be useful in advanced
scenarios:

* `--root <dir>` lets you specify the root directory of a website in which to
  run the command. This means you don't need to change the current working
  directory to that website, which can be necessary for scripting, for instance.

* `--pid-file <file>` creates a PID file containing the PieCrust process ID for
  the next command.


### Configuration Changes

Several global options relate to modifying the [website configuration][3]. This
is useful if you want to override some of the configuration settings
temporarily.

> When you modify the configuration like this, PieCrust has to use a different
> cache, because any change in the configuration can translate into any change
> in the generated content. This means that you may notice some commands not
> re-using cached outputs from previous commands.

* `--config <name>` lets you specify a *configuration variant* to apply before
  running the command. A *configuration variant* is a fragment of website config
  that lets you override what's defined normally in `config.yml`. For more
  information, see the [website configuration][3] page.

* `--config-set <name> <value>` lets you override _a specific configuration
  setting_.

[3]: {{docurl('general/website-configuration')}}


### Logging

Several global options relate to logging:

* `--quiet` will make PieCrust only print out very important messages
  or errors.
  
* `--debug` does the opposite, making PieCrust print lots of
  debugging information, including stack traces when errors occur -- which is
  useful for troubleshooting a problem.

* `--log` lets you log to a file. The complementary `--log-debug` lets you log
  debug information (like `--debug`) but only to the log file, which reduces
  spam in the console.

* `--no-color` suppresses colored output. This can be useful if you want to
  parse PieCrust's output without having to deal with weird ANSI color codes.

