---
title: Chef Commands
needs_pygments: true
---

To provide new `chef` commands, you need to override the `getCommands` method of
your plugin, and return command instances:


{% highlight 'python' %}
class MyPlugin(PieCrustPlugin):
    name = 'myplugin'

    def getCommands(self):
        return [
                MyNewCommand()]
{% endhighlight %}


To create a command class, inherit from the `ChefCommand` base class:

{% highlight 'python' %}
from piecrust.commands.base import ChefCommand


class MyNewCommand(ChefCommand):
    def __init__(self):
        super(MyNewCommand, self).__init__()
        self.name = 'foobar'
        self.description = "Does some foobar thing."

    def setupParser(self, parser, app):
        parser.add_argument('thing')

    def run(self, ctx):
        print("Doing %s" % ctx.args.thing)
{% endhighlight %}


* The `name` will be used for command line invocation, _i.e._ your new command
  will be invoked with `chef foobar`.
* The `description` will be used for help pages like `chef --help`.
* The `setupParser` method passes an `argparse.ArgumentParser` and a `PieCrust`
  application. You're supposed to setup the syntax for your commend there.
* The `run` method is called when your command is executed. The `ctx` object
  contains a couple useful things, among others:
    * `args` is the namespace obtained from running `parse_args`. It has all the
      values of the arguments for your command.
    * `app` is the instance of the current `PieCrust` application.
    * For the other things, check-out `piecrust.commands.base.CommandContext`.

