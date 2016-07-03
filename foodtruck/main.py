import logging


logger = logging.getLogger(__name__)


def run_foodtruck(host=None, port=None, debug=False):
    if debug:
        import foodtruck.settings
        foodtruck.settings.DEBUG = debug

    from .web import create_foodtruck_app
    try:
        app = create_foodtruck_app()
        app.run(host=host, port=port, debug=debug, threaded=True)
    except SystemExit:
        # This is needed for Werkzeug's code reloader to be able to correctly
        # shutdown the child process in order to restart it (otherwise, SSE
        # generators will keep it alive).
        from . import pubutil
        logger.debug("Shutting down SSE generators from main...")
        pubutil.server_shutdown = True
        raise

