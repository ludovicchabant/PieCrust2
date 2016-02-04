import logging
from piecrust.publishing.base import PublishingContext


logger = logging.getLogger(__name__)


class InvalidPublishTargetError(Exception):
    pass


class PublishingError(Exception):
    pass


class Publisher(object):
    def __init__(self, app):
        self.app = app

    def run(self, target, log_file=None):
        target_cfg = self.app.config.get('publish/%s' % target)
        if not target_cfg:
            raise InvalidPublishTargetError(
                    "No such publish target: %s" % target)

        target_type = target_cfg.get('type')
        if not target_type:
            raise InvalidPublishTargetError(
                    "Publish target '%s' doesn't specify a type." % target)

        pub = None
        for pub_cls in self.app.plugin_loader.getPublishers():
            if pub_cls.PUBLISHER_NAME == target_type:
                pub = pub_cls(self.app, target)
                break
        if pub is None:
            raise InvalidPublishTargetError(
                    "Publish target '%s' has invalid type: %s" %
                    (target, target_type))

        ctx = PublishingContext()

        hdlr = None
        if log_file:
            if not pub.is_using_custom_logging:
                logger.debug("Adding file handler for: %s" % log_file)
                hdlr = logging.FileHandler(log_file, mode='w', encoding='utf8')
                logger.addHandler(hdlr)
            else:
                logger.debug("Creating custom log file: %s" % log_file)
                ctx.custom_logging_file = open(
                        log_file, mode='w', encoding='utf8')

        intro_msg = ("Running publish target '%s' with publisher: %s" %
                     (target, pub.PUBLISHER_NAME))
        logger.debug(intro_msg)
        if ctx.custom_logging_file:
            ctx.custom_logging_file.write(intro_msg + "\n")

        try:
            success = pub.run(ctx)
        except Exception as ex:
            raise PublishingError(
                    "Error publishing to target: %s" % target) from ex
        finally:
            if ctx.custom_logging_file:
                ctx.custom_logging_file.close()
            if hdlr:
                logger.removeHandler(hdlr)
                hdlr.close()

        if not success:
            raise PublishingError(
                    "Unknown error publishing to target: %s" % target)

