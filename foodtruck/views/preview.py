import os.path
from flask import g, make_response
from flask.ext.login import login_required
from piecrust import CACHE_DIR
from piecrust.serving.server import Server
from ..web import app


@app.route('/site/<sitename>/')
@login_required
def preview_site_root(sitename):
    return preview_site(sitename, '/')


@app.route('/site/<sitename>/<path:url>')
@login_required
def preview_site(sitename, url):
    root_dir = g.sites.get_root_dir(sitename)
    sub_cache_dir = os.path.join(root_dir, CACHE_DIR, 'foodtruck')
    server = Server(root_dir, sub_cache_dir=sub_cache_dir,
                    root_url='/site/%s/' % sitename,
                    debug=app.debug)
    return make_response(server._run_request)


