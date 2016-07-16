import os.path
import copy
import logging
import yaml
from piecrust.configuration import (
        Configuration, ConfigurationError, ConfigurationLoader,
        merge_dicts)


logger = logging.getLogger(__name__)


def get_foodtruck_config(dirname=None, fallback_config=None):
    dirname = dirname or os.getcwd()
    cfg_path = os.path.join(dirname, 'foodtruck.yml')
    return FoodTruckConfiguration(cfg_path, fallback_config)


class FoodTruckConfigNotFoundError(Exception):
    pass


class FoodTruckConfiguration(Configuration):
    def __init__(self, cfg_path, fallback_config=None):
        super(FoodTruckConfiguration, self).__init__()
        self.cfg_path = cfg_path
        self.fallback_config = fallback_config

    def _load(self):
        try:
            with open(self.cfg_path, 'r', encoding='utf-8') as fp:
                values = yaml.load(
                        fp.read(),
                        Loader=ConfigurationLoader)

            self._values = self._validateAll(values)
        except OSError:
            if self.fallback_config is None:
                raise FoodTruckConfigNotFoundError()

            logger.debug("No FoodTruck configuration found, using fallback "
                         "configuration.")
            self._values = copy.deepcopy(self.fallback_config)
        except Exception as ex:
            raise ConfigurationError(
                    "Error loading configuration from: %s" %
                    self.cfg_path) from ex

    def _validateAll(self, values):
        if values is None:
            values = {}

        values = merge_dicts(copy.deepcopy(default_configuration), values)

        return values

    def save(self):
        with open(self.cfg_path, 'w', encoding='utf8') as fp:
            self.cfg.write(fp)


default_configuration = {
        'triggers': {
            'bake': 'chef bake'
            },
        'scm': {
            'type': 'hg'
            },
        'security': {
            'username': '',
            'password': ''
            }
        }

