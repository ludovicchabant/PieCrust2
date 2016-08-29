import os.path
import logging
from flask import Flask
from werkzeug import SharedDataMiddleware
from .blueprint import foodtruck_bp
from .configuration import FoodTruckConfigNotFoundError
from .sites import InvalidSiteError


logger = logging.getLogger(__name__)


def create_foodtruck_app(extra_settings=None):
    app = Flask(__name__.split('.')[0])
    app.config.from_object('piecrust.admin.settings')
    app.config.from_envvar('FOODTRUCK_SETTINGS', silent=True)
    if extra_settings:
        app.config.update(extra_settings)

    admin_root = app.config.setdefault('FOODTRUCK_ROOT', os.getcwd())
    config_path = os.path.join(admin_root, 'app.cfg')

    # If we're being run as the `chef admin run` command, from inside a PieCrust
    # website, do a few things differently.
    app.config['FOODTRUCK_PROCEDURAL_CONFIG'] = None
    if (app.config.get('FOODTRUCK_CMDLINE_MODE', False) and
            os.path.isfile(os.path.join(admin_root, 'config.yml'))):
        app.secret_key = os.urandom(22)
        app.config['LOGIN_DISABLED'] = True
        app.config['FOODTRUCK_PROCEDURAL_CONFIG'] = {
                'sites': {
                    'local': admin_root}
                }

    # Add a special route for the `.well-known` directory.
    app.wsgi_app = SharedDataMiddleware(
            app.wsgi_app,
            {'/.well-known': os.path.join(admin_root, '.well-known')})

    if os.path.isfile(config_path):
        app.config.from_pyfile(config_path)

    if app.config['DEBUG']:
        l = logging.getLogger()
        l.setLevel(logging.DEBUG)
    else:
        @app.errorhandler(FoodTruckConfigNotFoundError)
        def _on_config_missing(ex):
            return render_template('install.html')

        @app.errorhandler(InvalidSiteError)
        def _on_invalid_site(ex):
            data = {'error': "The was an error with your configuration file: %s" %
                    str(ex)}
            return render_template('error.html', **data)

    _missing_secret_key = False
    if not app.secret_key:
        # If there's no secret key, create a temp one but mark the app as not
        # correctly installed so it shows the installation information page.
        app.secret_key = 'temp-key'
        _missing_secret_key = True

    # Register extensions and blueprints.
    app.register_blueprint(foodtruck_bp)

    logger.debug("Created FoodTruck app with admin root: %s" % admin_root)

    return app

