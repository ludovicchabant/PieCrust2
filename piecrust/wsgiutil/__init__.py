import logging
from piecrust.serving.server import WsgiServer


def _setup_logging(log_file, log_level, max_log_bytes, log_backup_count):
    if log_file:
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(log_file, maxBytes=max_log_bytes,
                                      backupCount=log_backup_count)
        handler.setLevel(log_level)
        logging.getLogger().addHandler(handler)


def get_app(root_dir, *,
            cache_key='prod',
            enable_debug_info=False,
            log_file=None,
            log_level=logging.INFO,
            log_backup_count=0,
            max_log_bytes=4096):
    _setup_logging(log_file, log_level, max_log_bytes, log_backup_count)
    app = WsgiServer(root_dir,
                     cache_key=cache_key,
                     enable_debug_info=enable_debug_info)
    return app


def get_admin_app(root_dir, *,
                  url_prefix='pc-admin',
                  log_file=None,
                  log_level=logging.INFO,
                  log_backup_count=0,
                  max_log_bytes=4096):
    _setup_logging(log_file, log_level, max_log_bytes, log_backup_count)
    es = {
        'FOODTRUCK_ROOT': root_dir,
        'FOODTRUCK_URL_PREFIX': url_prefix}
    from piecrust.admin.web import create_foodtruck_app
    app = create_foodtruck_app(es)
    return app

