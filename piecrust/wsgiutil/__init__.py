import logging
from piecrust.serving.wrappers import get_piecrust_server


def _setup_logging(log_file, log_level, max_log_bytes, log_backup_count):
    if log_file:
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(log_file, maxBytes=max_log_bytes,
                                      backupCount=log_backup_count)
        handler.setLevel(log_level)
        logging.getLogger().addHandler(handler)


def get_app(root_dir, *,
            cache_key='prod',
            serve_admin=False,
            log_file=None,
            log_level=logging.INFO,
            log_backup_count=0,
            max_log_bytes=4096):
    _setup_logging(log_file, log_level, max_log_bytes, log_backup_count)
    app = get_piecrust_server(root_dir,
                              serve_site=True,
                              serve_admin=serve_admin,
                              cache_key=cache_key)
    return app


def get_admin_app(root_dir, *,
                  cache_key='prod',
                  log_file=None,
                  log_level=logging.INFO,
                  log_backup_count=0,
                  max_log_bytes=4096):
    _setup_logging(log_file, log_level, max_log_bytes, log_backup_count)
    app = get_piecrust_server(root_dir,
                              serve_site=False,
                              serve_admin=True,
                              cache_key=cache_key)
    return app

