import os.path
import logging
from flask import Flask
from werkzeug import SharedDataMiddleware


logger = logging.getLogger(__name__)


def create_foodtruck_app(extra_settings=None):
    from .blueprint import foodtruck_bp

    app = Flask(__name__.split('.')[0], static_folder=None)
    app.config.from_object('piecrust.admin.settings')
    app.config.from_envvar('FOODTRUCK_SETTINGS', silent=True)
    if extra_settings:
        app.config.update(extra_settings)

    root_dir = app.config.setdefault('FOODTRUCK_ROOT', os.getcwd())

    # Add a special route for the `.well-known` directory.
    app.wsgi_app = SharedDataMiddleware(
        app.wsgi_app,
        {'/.well-known': os.path.join(root_dir, '.well-known')})

    # Setup logging/error handling.
    if app.config['DEBUG']:
        l = logging.getLogger()
        l.setLevel(logging.DEBUG)

    if not app.config['SECRET_KEY']:
        # If there's no secret key, create a temp one but mark the app as not
        # correctly installed so it shows the installation information page.
        app.config['SECRET_KEY'] = 'temp-key'

    # Register extensions and blueprints.
    bp_prefix = app.config['FOODTRUCK_URL_PREFIX']
    app.register_blueprint(foodtruck_bp, url_prefix=bp_prefix)

    logger.debug("Created FoodTruck app with admin root: %s" % root_dir)

    return app

