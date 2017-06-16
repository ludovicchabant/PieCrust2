import os.path
import time
import logging
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

    def run(self, target,
            force=False, preview=False, extra_args=None, log_file=None,
            applied_config_variant=None, applied_config_values=None):
        start_time = time.perf_counter()

        # Get publisher for this target.
        pub = self.app.getPublisher(target)
        if pub is None:
            raise InvalidPublishTargetError(
                "No such publish target: %s" % target)

        # Will we need to bake first?
        bake_first = True
        if not pub.has_url_config:
            bake_first = pub.getConfigValue('bake', True)

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
        rec1 = None
        rec2 = None
        was_baked = False
        bake_out_dir = os.path.join(self.app.root_dir, '_pub', target)
        if bake_first:
            if not preview:
                bake_start_time = time.perf_counter()
                logger.debug("Baking first to: %s" % bake_out_dir)

                from piecrust.baking.baker import Baker
                baker = Baker(
                    self.app, bake_out_dir,
                    applied_config_variant=applied_config_variant,
                    applied_config_values=applied_config_values)
                rec1 = baker.bake()

                from piecrust.processing.pipeline import ProcessorPipeline
                proc = ProcessorPipeline(
                    self.app, bake_out_dir,
                    applied_config_variant=applied_config_variant,
                    applied_config_values=applied_config_values)
                rec2 = proc.run()

                was_baked = True

                if not rec1.success or not rec2.success:
                    raise Exception(
                        "Error during baking, aborting publishing.")
                logger.info(format_timed(bake_start_time, "Baked website."))
            else:
                logger.info("Would bake to: %s" % bake_out_dir)

        # Publish!
        logger.debug(
            "Running publish target '%s' with publisher: %s" %
            (target, pub.PUBLISHER_NAME))
        pub_start_time = time.perf_counter()

        ctx = PublishingContext()
        ctx.bake_out_dir = bake_out_dir
        ctx.bake_record = rec1
        ctx.processing_record = rec2
        ctx.was_baked = was_baked
        ctx.preview = preview
        ctx.args = extra_args
        try:
            pub.run(ctx)
        except Exception as ex:
            raise PublishingError(
                "Error publishing to target: %s" % target) from ex
        finally:
            if hdlr:
                root_logger.removeHandler(hdlr)
                hdlr.close()

        logger.info(format_timed(
            pub_start_time, "Ran publisher %s" % pub.PUBLISHER_NAME))

        logger.info(format_timed(start_time, 'Deployed to %s' % target))


def find_publisher_class(app, name, is_scheme=False):
    attr_name = 'PUBLISHER_SCHEME' if is_scheme else 'PUBLISHER_NAME'
    for pub_cls in app.plugin_loader.getPublishers():
        pub_sch = getattr(pub_cls, attr_name, None)
        if pub_sch == name:
            return pub_cls
    return None


def find_publisher_name(app, scheme):
    pub_cls = find_publisher_class(app, scheme, True)
    if pub_cls:
        return pub_cls.PUBLISHER_NAME
    return None

