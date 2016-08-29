import os
import os.path
import time
import logging
from flask import Blueprint, current_app, g, request, render_template
from .configuration import (
        FoodTruckConfigNotFoundError, get_foodtruck_config)
from .sites import FoodTruckSites, InvalidSiteError


logger = logging.getLogger(__name__)


# Prepare the Login extension.
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
login_manager.login_view = 'FoodTruck.login'
login_manager.user_loader(load_user)


def record_login_manager(state):
    if state.app.secret_key == 'temp-key':
        def _handler():
            raise FoodTruckConfigNotFoundError()

        logger.debug("No secret key found, disabling website login.")
        login_manager.unauthorized_handler(_handler)
        login_manager.login_view = None

    login_manager.init_app(state.app)


# Setup Bcrypt.
from .bcryptfallback import Bcrypt
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
    def _get_config():
        admin_root = current_app.config['FOODTRUCK_ROOT']
        procedural_config = current_app.config['FOODTRUCK_PROCEDURAL_CONFIG']
        return get_foodtruck_config(admin_root, procedural_config)

    def _get_sites():
        names = g.config.get('sites')
        if not names or not isinstance(names, dict):
            raise InvalidSiteError(
                    "No sites are defined in the configuration file.")

        current = request.cookies.get('foodtruck_site_name')
        if current is not None and current not in names:
            current = None
        if current is None:
            current = next(iter(names.keys()))
        s = FoodTruckSites(g.config, current)
        return s

    def _get_current_site():
        return g.sites.get()

    g.config = LazySomething(_get_config)
    g.sites = LazySomething(_get_sites)
    g.site = LazySomething(_get_current_site)


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
import piecrust.admin.views.menu  # NOQA
import piecrust.admin.views.preview  # NOQA
import piecrust.admin.views.publish  # NOQA
import piecrust.admin.views.sources  # NOQA


