# This is a utility module that can be used with any WSGI-compatible server
# like Werkzeug or Gunicorn. It returns a WSGI app for serving a PieCrust
# administration panel located in the current working directory.
import os
from piecrust.wsgiutil import get_admin_app


root_dir = os.getcwd()
app = get_admin_app(root_dir)
# Add this for `mod_wsgi`.
application = app


