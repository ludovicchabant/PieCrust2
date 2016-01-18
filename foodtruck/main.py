import logging


logger = logging.getLogger(__name__)


def run_foodtruck(debug=False):
    from .web import app
    try:
        app.run(debug=debug, threaded=True)
    except SystemExit:
        # This is needed for Werkzeug's code reloader to be able to correctly
        # shutdown the child process in order to restart it (otherwise, SSE
        # generators will keep it alive).
        from .views import baking
        logger.debug("Shutting down SSE generators from main...")
        baking.server_shutdown = True
        raise

