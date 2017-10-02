import os.path
import logging
from werkzeug.utils import secure_filename
from flask import (
    g, request, abort, render_template, url_for, redirect, flash)
from flask.ext.login import login_required
from piecrust.data.assetor import Assetor
from piecrust.serving.util import get_requested_page
from ..blueprint import foodtruck_bp
from ..views import with_menu_context


logger = logging.getLogger(__name__)


@foodtruck_bp.route('/edit/', defaults={'uri': ''}, methods=['GET', 'POST'])
@foodtruck_bp.route('/edit/<path:uri>', methods=['GET', 'POST'])
@login_required
def edit_page(uri):
    site = g.site
    pcapp = site.piecrust_app
    rp = get_requested_page(pcapp, '%s/preview/%s' % (site.url_prefix, uri))
    page = rp.page
    if page is None:
        abort(404)

    if request.method == 'POST':
        return _submit_page_form(page, uri)

    return _edit_page_form(page, uri)


def _edit_page_form(page, uri):
    data = {}
    data['is_new_page'] = False
    data['url_postback'] = url_for('.edit_page', uri=uri)
    data['url_upload_asset'] = url_for('.upload_page_asset', uri=uri)
    data['url_preview'] = page.getUri()
    data['url_cancel'] = url_for(
        '.list_source', source_name=page.source.name)

    with page.source.openItem(page.content_item, 'r') as fp:
        data['page_text'] = fp.read()
    data['is_dos_nl'] = "1" if '\r\n' in data['page_text'] else "0"

    assetor = Assetor(page)
    assets_data = []
    for n in assetor._getAssetNames():
        assets_data.append({'name': n, 'url': assetor[n]})
    data['assets'] = assets_data

    data['has_scm'] = (g.site.scm is not None)

    with_menu_context(data)
    return render_template('edit_page.html', **data)


def _submit_page_form(page, uri):
    page_text = request.form['page_text']
    if request.form['is_dos_nl'] == '0':
        page_text = page_text.replace('\r\n', '\n')

    if 'do_save' in request.form or 'do_save_and_commit' in request.form:
        logger.debug("Writing page: %s" % page.content_spec)
        with page.source.openItem(page.content_item, 'w') as fp:
            fp.write(page_text)
        flash("%s was saved." % page.content_spec)

    scm = g.site.scm
    if 'do_save_and_commit' in request.form and scm is not None:
        message = request.form.get('commit_msg')
        if not message:
            message = "Edit %s" % page.content_spec
        scm.commit([page.content_spec], message)

    if 'do_save' in request.form or 'do_save_and_commit' in request.form:
        return _edit_page_form(page, uri)

    abort(400)


@foodtruck_bp.route('/upload/<path:uri>', methods=['POST'])
def upload_page_asset(uri):
    if 'ft-asset-file' not in request.files:
        return redirect(url_for('.edit_page', uri=uri))

    asset_file = request.files['ft-asset-file']
    if asset_file.filename == '':
        return redirect(url_for('.edit_page', uri=uri))

    site = g.site
    pcapp = site.piecrust_app
    rp = get_requested_page(pcapp,
                            '/site/%s/%s' % (g.sites.current_site, uri))
    page = rp.qualified_page
    if page is None:
        abort(404)

    filename = asset_file.filename
    if request.form['ft-asset-name']:
        _, ext = os.path.splitext(filename)
        filename = request.form['ft-asset-name'] + ext
    filename = secure_filename(filename)
    dirname, _ = os.path.splitext(page.path)
    dirname += '-assets'
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    asset_path = os.path.join(dirname, filename)
    logger.info("Uploading file to: %s" % asset_path)
    asset_file.save(asset_path)
    return redirect(url_for('.edit_page', uri=uri))
