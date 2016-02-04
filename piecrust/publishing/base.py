

class PublishingContext(object):
    def __init__(self):
        self.custom_logging_file = None


class Publisher(object):
    def __init__(self, app, target):
        self.app = app
        self.target = target
        self.is_using_custom_logging = False
        self.log_file_path = None

    def getConfig(self):
        return self.app.config.get('publish/%s' % self.target)

    def getConfigValue(self, name):
        return self.app.config.get('publish/%s/%s' % (self.target, name))

    def run(self, ctx):
        raise NotImplementedError()

