from flask import g, request, make_response
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
    site = g.site
    pcappfac = site.piecrust_factory
    root_url = request.script_root or ''
    root_url += site.make_url('/preview/')
    server = PieCrustServer(pcappfac, root_url=root_url)

    # Patch the WSGI environment for the underlying PieCrust server,
    # because it doesn't generally handle stuff being under a different
    # sub folder of the domain.
    script_name = request.environ['SCRIPT_NAME']
    request.environ['SCRIPT_NAME'] = ''
    request.environ['PATH_INFO'] = script_name + request.environ['PATH_INFO']

    return make_response(server)

