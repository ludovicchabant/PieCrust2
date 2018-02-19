import time
import logging
from flask import Blueprint, current_app, g
from .siteinfo import SiteInfo


logger = logging.getLogger(__name__)


# Prepare the Login extension.
from flask.ext.login import LoginManager, UserMixin  # NOQA


class User(UserMixin):
    def __init__(self, uid, pwd):
        self.id = uid
        self.password = pwd


def load_user(user_id):
    admin_id = current_app.config.get('USERNAME')
    if admin_id == user_id:
        admin_pwd = current_app.config.get('PASSWORD')
        return User(admin_id, admin_pwd)
    return None


def record_login_manager(state):
    login_manager = LoginManager()
    login_manager.login_view = 'FoodTruck.login'
    login_manager.user_loader(load_user)

    if state.app.config['SECRET_KEY'] == 'temp-key':
        def _handler():
            from flask import render_template
            return render_template(
                'error.html',
                error="No secret key has been set!")

        logger.debug("No secret key found, disabling website login.")
        login_manager.unauthorized_handler(_handler)
        login_manager.login_view = None

    login_manager.init_app(state.app)


# Setup Bcrypt.
from .bcryptfallback import Bcrypt  # NOQA
bcrypt_ext = Bcrypt()


def record_bcrypt(state):
    if (getattr(Bcrypt, 'is_fallback_bcrypt', None) is True and
            not state.app.config.get('FOODTRUCK_CMDLINE_MODE', False)):
        raise Exception(
            "You're running FoodTruck outside of `chef`, and will need to "
            "install Flask-Bcrypt to get more proper security.")

    bcrypt_ext.init_app(state.app)
    state.app.bcrypt = bcrypt_ext


# Create the FoodTruck blueprint.
foodtruck_bp = Blueprint(
    'FoodTruck', __name__,
    template_folder='templates',
    static_folder='static')

foodtruck_bp.record(record_login_manager)
foodtruck_bp.record(record_bcrypt)


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


@foodtruck_bp.before_request
def _setup_foodtruck_globals():
    def _get_site():
        root_dir = current_app.config['FOODTRUCK_ROOT_DIR']
        return SiteInfo(root_dir,
                        url_prefix=foodtruck_bp.url_prefix,
                        debug=current_app.debug)

    g.site = LazySomething(_get_site)


@foodtruck_bp.after_request
def _call_after_request_callbacks(response):
    for callback in getattr(g, 'after_request_callbacks', ()):
        callback(response)
    return response


@foodtruck_bp.errorhandler
def _on_error(ex):
    logging.exception(ex)


@foodtruck_bp.app_template_filter('iso8601')
def timestamp_to_iso8601(t):
    t = time.localtime(t)
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', t)


@foodtruck_bp.app_template_filter('datetime')
def timestamp_to_datetime(t, fmt=None):
    fmt = fmt or '%x'
    t = time.localtime(t)
    return time.strftime(fmt, t)


import piecrust.admin.views.create  # NOQA
import piecrust.admin.views.dashboard  # NOQA
import piecrust.admin.views.edit  # NOQA
import piecrust.admin.views.mentions  # NOQA
import piecrust.admin.views.menu  # NOQA
import piecrust.admin.views.micropub  # NOQA
import piecrust.admin.views.preview  # NOQA
import piecrust.admin.views.publish  # NOQA
import piecrust.admin.views.sources  # NOQA
