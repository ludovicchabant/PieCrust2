from flask import current_app, g, make_response
from flask.ext.login import login_required
from piecrust.serving.server import PieCrustServer
from ..blueprint import foodtruck_bp


@foodtruck_bp.route('/preview/')
@login_required
def preview_root_page():
    return preview_page('/')


@foodtruck_bp.route('/preview/<path:url>')
@login_required
def preview_page(url):
    pcappfac = g.site.piecrust_factory
    url_prefix = current_app.config['FOODTRUCK_URL_PREFIX']
    server = PieCrustServer(pcappfac,
                            root_url='%s/preview/' % url_prefix)
    return make_response(server)

