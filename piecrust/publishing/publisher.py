import os.path
import time
import logging
import urllib.parse
from piecrust.chefutil import format_timed
from piecrust.publishing.base import PublishingContext


logger = logging.getLogger(__name__)


class InvalidPublishTargetError(Exception):
    pass


class PublishingError(Exception):
    pass


class Publisher(object):
    def __init__(self, app):
        self.app = app

    def run(self, target, preview=False, log_file=None):
        start_time = time.perf_counter()

        # Get the configuration for this target.
        target_cfg = self.app.config.get('publish/%s' % target)
        if not target_cfg:
            raise InvalidPublishTargetError(
                    "No such publish target: %s" % target)

        target_type = None
        bake_first = True
        parsed_url = None
        if isinstance(target_cfg, dict):
            target_type = target_cfg.get('type')
            if not target_type:
                raise InvalidPublishTargetError(
                        "Publish target '%s' doesn't specify a type." % target)
            bake_first = target_cfg.get('bake', True)
        elif isinstance(target_cfg, str):
            comps = urllib.parse.urlparse(target_cfg)
            if not comps.scheme:
                raise InvalidPublishTargetError(
                        "Publish target '%s' has an invalid target URL." %
                        target)
            parsed_url = comps
            target_type = find_publisher_name(self.app, comps.scheme)
            if target_type is None:
                raise InvalidPublishTargetError(
                        "No such publish target scheme: %s" % comps.scheme)

        # Setup logging stuff.
        hdlr = None
        root_logger = logging.getLogger()
        if log_file and not preview:
            logger.debug("Adding file handler for: %s" % log_file)
            hdlr = logging.FileHandler(log_file, mode='w', encoding='utf8')
            root_logger.addHandler(hdlr)
        if not preview:
            logger.info("Deploying to %s" % target)
        else:
            logger.info("Previewing deployment to %s" % target)

        # Bake first is necessary.
        bake_out_dir = None
        if bake_first:
            bake_out_dir = os.path.join(self.app.cache_dir, 'pub', target)
            if not preview:
                bake_start_time = time.perf_counter()
                logger.debug("Baking first to: %s" % bake_out_dir)

                from piecrust.baking.baker import Baker
                baker = Baker(self.app, bake_out_dir)
                rec1 = baker.bake()

                from piecrust.processing.pipeline import ProcessorPipeline
                proc = ProcessorPipeline(self.app, bake_out_dir)
                rec2 = proc.run()

                if not rec1.success or not rec2.success:
                    raise Exception(
                            "Error during baking, aborting publishing.")
                logger.info(format_timed(bake_start_time, "Baked website."))
            else:
                logger.info("Would bake to: %s" % bake_out_dir)

        # Create the appropriate publisher.
        pub = None
        for pub_cls in self.app.plugin_loader.getPublishers():
            if pub_cls.PUBLISHER_NAME == target_type:
                pub = pub_cls(self.app, target)
                break
        if pub is None:
            raise InvalidPublishTargetError(
                    "Publish target '%s' has invalid type: %s" %
                    (target, target_type))
        pub.parsed_url = parsed_url

        # Publish!
        logger.debug(
                "Running publish target '%s' with publisher: %s" %
                (target, pub.PUBLISHER_NAME))
        pub_start_time = time.perf_counter()

        ctx = PublishingContext()
        ctx.bake_out_dir = bake_out_dir
        ctx.preview = preview
        try:
            success = pub.run(ctx)
        except Exception as ex:
            raise PublishingError(
                    "Error publishing to target: %s" % target) from ex
        finally:
            if hdlr:
                root_logger.removeHandler(hdlr)
                hdlr.close()

        if not success:
            raise PublishingError(
                    "Unknown error publishing to target: %s" % target)
        logger.info(format_timed(
            pub_start_time, "Ran publisher %s" % pub.PUBLISHER_NAME))

        logger.info(format_timed(start_time, 'Deployed to %s' % target))


def find_publisher_class(app, scheme):
    for pub_cls in app.plugin_loader.getPublishers():
        pub_sch = getattr(pub_cls, 'PUBLISHER_SCHEME', None)
        if ('bake+%s' % pub_sch) == scheme:
            return pub_cls
    return None


def find_publisher_name(app, scheme):
    pub_cls = find_publisher_class(app, scheme)
    if pub_cls:
        return pub_cls.PUBLISHER_NAME
    return None

