import logging


logger = logging.getLogger()


def get_wsgi_app(admin_root=None, log_file=None,
                 max_log_bytes=4096, log_backup_count=0,
                 log_level=logging.INFO):
    if log_file:
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(log_file, maxBytes=max_log_bytes,
                                      backupCount=log_backup_count)
        handler.setLevel(log_level)
        logging.getLogger().addHandler(handler)

    logger.debug("Creating WSGI application.")
    es = {}
    if admin_root:
        es['FOODTRUCK_ROOT'] = admin_root
    from .web import create_foodtruck_app
    app = create_foodtruck_app(es)
    return app

