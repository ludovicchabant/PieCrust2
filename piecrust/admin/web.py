import os.path
import logging
from flask import Flask


logger = logging.getLogger(__name__)


def create_foodtruck_app(extra_settings=None, url_prefix=None):
    from .blueprint import foodtruck_bp

    app = Flask(__name__.split('.')[0], static_folder=None)
    app.config.from_object('piecrust.admin.settings')
    if extra_settings:
        app.config.update(extra_settings)

    root_dir = app.config.setdefault('FOODTRUCK_ROOT_DIR', os.getcwd())

    app.config.from_pyfile(os.path.join(root_dir, 'admin_app.cfg'),
                           silent=True)
    app.config.from_envvar('FOODTRUCK_SETTINGS', silent=True)

    # Setup logging/error handling.
    if app.config['DEBUG']:
        l = logging.getLogger()
        l.setLevel(logging.DEBUG)

    if not app.config['SECRET_KEY']:
        # If there's no secret key, create a temp one but mark the app as not
        # correctly installed so it shows the installation information page.
        app.config['SECRET_KEY'] = 'temp-key'

    # Register extensions and blueprints.
    app.register_blueprint(foodtruck_bp, url_prefix=url_prefix)

    # Debugging stuff
    if app.config.get('FOODTRUCK_DEBUG_404'):
        @app.errorhandler(404)
        def page_not_found(e):
            return _debug_page_not_found(app, e)

    logger.debug("Created FoodTruck app with admin root: %s" % root_dir)

    return app


def _debug_page_not_found(app, e):
    from flask import request, url_for
    output = []
    for rule in app.url_map.iter_rules():
        options = {}
        for arg in rule.arguments:
            options[arg] = "[{0}]".format(arg)
            methods = ','.join(rule.methods)
            try:
                url = url_for(rule.endpoint, **options)
            except:
                url = '???'
            line = ("{:50s} {:20s} {}".format(rule.endpoint, methods, url))
            output.append(line)

    resp = 'FOODTRUCK_ROOT_URL=%s<br/>\n' % str(
        app.config['FOODTRUCK_ROOT_URL'])
    resp += 'PATH=%s<br/>\n' % request.path
    resp += 'ENVIRON=%s<br/>\n' % str(request.environ)
    resp += 'URL RULES:<br/>\n'
    resp += '<br/>\n'.join(sorted(output))
    return resp, 404
