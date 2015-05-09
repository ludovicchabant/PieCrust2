# This is a utility module that can be used with any WSGI-compatible server
# like Werkzeug or Gunicorn. It returns a WSGI app for serving a PieCrust
# website located in the current working directory.
import os
from piecrust.serving.server import Server


root_dir = os.getcwd()
server = Server(root_dir, sub_cache_dir='prod', enable_debug_info=False)
app = server.getWsgiApp()
# Add this for `mod_wsgi`.
application = app

