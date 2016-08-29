import hashlib
import logging


print_warning = False
logger = logging.getLogger(__name__)


try:
    from bcrypt import hashpw, gensalt
except ImportError:
    print_warning = True

    def hashpw(password, *args, **kwargs):
        return hashlib.sha512(password).hexdigest().encode('utf8')

    def gensalt(*args, **kwargs):
        return b''


try:
    from flask.ext.bcrypt import Bcrypt
except ImportError:
    print_warning = True

    def generate_password_hash(password):
        return hashlib.sha512(password.encode('utf8')).hexdigest()

    def check_password_hash(reference, check):
        check_hash = hashlib.sha512(check.encode('utf8')).hexdigest()
        return check_hash == reference

    class SHA512Fallback(object):
        is_fallback_bcrypt = True

        def __init__(self, app=None):
            self.generate_password_hash = generate_password_hash
            self.check_password_hash = check_password_hash

        def init_app(self, app):
            app.bcrypt = self

    Bcrypt = SHA512Fallback


if print_warning:
    logging.warning("Bcrypt not available... falling back to SHA512.")
    logging.warning("Run `pip install Flask-Bcrypt` for more secure "
                    "password hashing.")

