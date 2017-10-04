from flask import g, make_response
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
    server = PieCrustServer(pcappfac, root_url=g.site.make_url('/preview/'))
    return make_response(server)

