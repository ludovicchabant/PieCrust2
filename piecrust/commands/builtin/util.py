import os
import os.path
import codecs
import logging
import yaml
from piecrust.app import CONFIG_PATH
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class InitCommand(ChefCommand):
    def __init__(self):
        super(InitCommand, self).__init__()
        self.name = 'init'
        self.description = "Creates a new empty PieCrust website."
        self.requires_website = False

    def setupParser(self, parser):
        parser.add_argument('destination',
                help="The destination directory in which to create the website.")

    def run(self, ctx):
        destination = ctx.args.destination
        if destination is None:
            destination = os.getcwd()

        if not os.path.isdir(destination):
            os.makedirs(destination, 0755)
        
        config_path = os.path.join(destination, CONFIG_PATH)
        if not os.path.isdir(os.path.dirname(config_path)):
            os.makedirs(os.path.dirname(config_path))

        config_text = yaml.dump({
                'site': {
                    'title': "My New Website",
                    'description': "A website recently generated with PieCrust",
                    'pretty_urls': True
                    },
                'smartypants': {
                    'enable': True
                    }
                },
                default_flow_style=False)
        with codecs.open(config_path, 'w', 'utf-8') as fp:
            fp.write(config_text)
        
