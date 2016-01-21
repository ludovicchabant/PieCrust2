import os
import os.path
import logging
from flask import Flask, g, request, render_template
from .config import (
        FoodTruckConfigNotFoundError, get_foodtruck_config)
from .sites import FoodTruckSites


logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object('foodtruck.settings')
app.config.from_envvar('FOODTRUCK_SETTINGS', silent=True)

admin_root = app.config['FOODTRUCK_ROOT'] or os.getcwd()
config_path = os.path.join(admin_root, 'app.cfg')
if os.path.isfile(config_path):
    app.config.from_pyfile(config_path)

if app.config['DEBUG']:
    l = logging.getLogger()
    l.setLevel(logging.DEBUG)

app.logger.debug("Using FoodTruck admin root: %s" % admin_root)


def after_this_request(f):
    if not hasattr(g, 'after_request_callbacks'):
        g.after_request_callbacks = []
    g.after_request_callbacks.append(f)
    return f


class LazySomething(object):
    def __init__(self, factory):
        self._factory = factory
        self._something = None

    def __getattr__(self, name):
        if self._something is not None:
            return getattr(self._something, name)

        self._something = self._factory()
        return getattr(self._something, name)


@app.before_request
def _setup_foodtruck_globals():
    def _get_config():
        return get_foodtruck_config(admin_root)

    def _get_sites():
        current = request.cookies.get('foodtruck_site_name')
        if current is None:
            names = g.config.get('sites')
            if not names or not isinstance(names, dict):
                raise FoodTruckConfigNotFoundError()
            current = next(iter(names.keys()))
        s = FoodTruckSites(g.config, current)
        return s

    g.config = LazySomething(_get_config)
    g.sites = LazySomething(_get_sites)


@app.after_request
def _call_after_request_callbacks(response):
    for callback in getattr(g, 'after_request_callbacks', ()):
        callback(response)
    return response


@app.errorhandler(FoodTruckConfigNotFoundError)
def _on_config_missing(ex):
    return render_template('install.html')


@app.errorhandler
def _on_error(ex):
    logging.exception(ex)


from flask.ext.login import LoginManager, UserMixin


class User(UserMixin):
    def __init__(self, uid, pwd):
        self.id = uid
        self.password = pwd


def load_user(user_id):
    admin_id = g.config.get('security/username')
    if admin_id == user_id:
        admin_pwd = g.config.get('security/password')
        return User(admin_id, admin_pwd)
    return None


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.user_loader(load_user)


try:
    from flask.ext.bcrypt import Bcrypt
except ImportError:
    logging.warning("Bcrypt not available... falling back to SHA512.")
    logging.warning("Run `pip install Flask-Bcrypt` for more secure "
                    "password hashing.")

    import hashlib

    def generate_password_hash(password):
        return hashlib.sha512(password.encode('utf8')).hexdigest()

    def check_password_hash(reference, check):
        check_hash = hashlib.sha512(check.encode('utf8')).hexdigest()
        return check_hash == reference

    class SHA512Fallback(object):
        def __init__(self, app=None):
            self.generate_password_hash = generate_password_hash
            self.check_password_hash = check_password_hash

    Bcrypt = SHA512Fallback

app.bcrypt = Bcrypt(app)


import foodtruck.views.baking  # NOQA
import foodtruck.views.create  # NOQA
import foodtruck.views.edit  # NOQA
import foodtruck.views.main  # NOQA
import foodtruck.views.menu  # NOQA
import foodtruck.views.preview  # NOQA
import foodtruck.views.settings  # NOQA
import foodtruck.views.sources  # NOQA

