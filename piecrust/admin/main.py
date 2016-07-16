import logging


logger = logging.getLogger(__name__)


def run_foodtruck(host=None, port=None, debug=False, extra_settings=None):
    es = {}
    if debug:
        es['DEBUG'] = True
    if extra_settings:
        es.update(extra_settings)

    from .web import create_foodtruck_app
    try:
        app = create_foodtruck_app(es)
        app.run(host=host, port=port, debug=debug, threaded=True)
    except SystemExit:
        # This is needed for Werkzeug's code reloader to be able to correctly
        # shutdown the child process in order to restart it (otherwise, SSE
        # generators will keep it alive).
        from . import pubutil
        logger.debug("Shutting down SSE generators from main...")
        pubutil.server_shutdown = True
        raise

