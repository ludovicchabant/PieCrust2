import os.path
import time
import logging
from piecrust.chefutil import format_timed


logger = logging.getLogger(__name__)


FILE_MODIFIED = 1
FILE_DELETED = 2


class PublisherConfigurationError(Exception):
    pass


class PublishingContext:
    def __init__(self):
        self.bake_out_dir = None
        self.bake_records = None
        self.processing_record = None
        self.was_baked = False
        self.preview = False
        self.args = None


class Publisher:
    PUBLISHER_NAME = 'undefined'
    PUBLISHER_SCHEME = None

    def __init__(self, app, target, config):
        self.app = app
        self.target = target
        self.config = config
        self.log_file_path = None

    def setupPublishParser(self, parser, app):
        return

    def parseUrlTarget(self, url):
        raise NotImplementedError()

    def run(self, ctx):
        raise NotImplementedError()

    def getBakedFiles(self, ctx):
        for rec in ctx.bake_records.records:
            for e in rec.getEntries():
                paths = e.getAllOutputPaths()
                if paths is not None:
                    yield from paths

    def getDeletedFiles(self, ctx):
        for rec in ctx.bake_records.records:
            yield from rec.deleted_out_paths


class InvalidPublishTargetError(Exception):
    pass


class PublishingError(Exception):
    pass


class PublishingManager:
    def __init__(self, appfactory, app):
        self.appfactory = appfactory
        self.app = app

    def run(self, target,
            force=False, preview=False, extra_args=None,
            log_file=None, log_debug_info=False, append_log_file=False):
        start_time = time.perf_counter()

        # Get publisher for this target.
        pub = self.app.getPublisher(target)
        if pub is None:
            raise InvalidPublishTargetError(
                "No such publish target: %s" % target)

        # Will we need to bake first?
        bake_first = pub.config.get('bake', True)

        # Setup logging stuff.
        hdlr = None
        root_logger = logging.getLogger()
        if log_file and not preview:
            logger.debug("Adding file handler for: %s" % log_file)
            mode = 'w'
            if append_log_file:
                mode = 'a'
            hdlr = logging.FileHandler(log_file, mode=mode, encoding='utf8')
            root_logger.addHandler(hdlr)

        if log_debug_info:
            _log_debug_info(target, force, preview, extra_args)

        if not preview:
            logger.info("Deploying to %s" % target)
        else:
            logger.info("Previewing deployment to %s" % target)

        # Bake first is necessary.
        records = None
        was_baked = False
        bake_out_dir = os.path.join(self.app.root_dir, '_pub', target)
        if bake_first:
            if not preview:
                bake_start_time = time.perf_counter()
                logger.debug("Baking first to: %s" % bake_out_dir)

                from piecrust.baking.baker import Baker
                baker = Baker(
                    self.appfactory, self.app, bake_out_dir, force=force)
                records = baker.bake()
                was_baked = True

                if not records.success:
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

        success = False
        ctx = PublishingContext()
        ctx.bake_out_dir = bake_out_dir
        ctx.bake_records = records
        ctx.was_baked = was_baked
        ctx.preview = preview
        ctx.args = extra_args
        try:
            success = pub.run(ctx)
        except Exception as ex:
            raise PublishingError(
                "Error publishing to target: %s" % target) from ex
        finally:
            if hdlr:
                root_logger.removeHandler(hdlr)
                hdlr.close()

        logger.info(format_timed(
            pub_start_time, "Ran publisher %s" % pub.PUBLISHER_NAME))

        if success:
            logger.info(format_timed(start_time, 'Deployed to %s' % target))
            return 0
        else:
            logger.error(format_timed(start_time, 'Failed to deploy to %s' %
                                      target))
            return 1


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


def _log_debug_info(target, force, preview, extra_args):
    import os
    import sys

    logger.info("---- DEBUG INFO START ----")
    logger.info("System:")
    logger.info("  sys.argv=%s" % sys.argv)
    logger.info("  sys.base_exec_prefix=%s" % sys.base_exec_prefix)
    logger.info("  sys.base_prefix=%s" % sys.base_prefix)
    logger.info("  sys.exec_prefix=%s" % sys.exec_prefix)
    logger.info("  sys.executable=%s" % sys.executable)
    logger.info("  sys.path=%s" % sys.path)
    logger.info("  sys.platform=%s" % sys.platform)
    logger.info("  sys.prefix=%s" % sys.prefix)
    logger.info("Environment:")
    logger.info("  cwd=%s" % os.getcwd())
    logger.info("  pid=%s" % os.getpid())
    logger.info("Variables:")
    for k, v in os.environ.items():
        logger.info("  %s=%s" % (k, v))
    logger.info("---- DEBUG INFO END ----")

