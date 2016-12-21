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


@foodtruck_bp.route('/edit/', defaults={'slug': ''}, methods=['GET', 'POST'])
@foodtruck_bp.route('/edit/<path:slug>', methods=['GET', 'POST'])
@login_required
def edit_page(slug):
    site = g.site
    site_app = site.piecrust_app
    rp = get_requested_page(site_app,
                            '/site/%s/%s' % (g.sites.current_site, slug))
    page = rp.qualified_page
    if page is None:
        abort(404)

    if request.method == 'POST':
        page_text = request.form['page_text']
        if request.form['is_dos_nl'] == '0':
            page_text = page_text.replace('\r\n', '\n')

        if 'do_save' in request.form or 'do_save_and_commit' in request.form:
            logger.debug("Writing page: %s" % page.path)
            with open(page.path, 'w', encoding='utf8', newline='') as fp:
                fp.write(page_text)
            flash("%s was saved." % os.path.relpath(
                page.path, site_app.root_dir))

        if 'do_save_and_commit' in request.form:
            message = request.form.get('commit_msg')
            if not message:
                message = "Edit %s" % os.path.relpath(
                    page.path, site_app.root_dir)
            if site.scm:
                site.scm.commit([page.path], message)

        if 'do_save' in request.form or 'do_save_and_commit' in request.form:
            return _edit_page_form(page, slug, site.name)

        abort(400)

    return _edit_page_form(page, slug, site.name)


@foodtruck_bp.route('/upload/<path:slug>', methods=['POST'])
def upload_page_asset(slug):
    if 'ft-asset-file' not in request.files:
        return redirect(url_for('.edit_page', slug=slug))

    asset_file = request.files['ft-asset-file']
    if asset_file.filename == '':
        return redirect(url_for('.edit_page', slug=slug))

    site = g.site
    site_app = site.piecrust_app
    rp = get_requested_page(site_app,
                            '/site/%s/%s' % (g.sites.current_site, slug))
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
    return redirect(url_for('.edit_page', slug=slug))


def _edit_page_form(page, slug, sitename):
    data = {}
    data['is_new_page'] = False
    data['url_postback'] = url_for('.edit_page', slug=slug)
    data['url_upload_asset'] = url_for('.upload_page_asset', slug=slug)
    data['url_preview'] = page.getUri()
    data['url_cancel'] = url_for(
        '.list_source', source_name=page.source.name)
    with open(page.path, 'r', encoding='utf8', newline='') as fp:
        data['page_text'] = fp.read()
    data['is_dos_nl'] = "1" if '\r\n' in data['page_text'] else "0"

    page.app.env.base_asset_url_format = \
        page.app.config.get('site/root') + '_asset/%path%'
    assetor = Assetor(page, 'blah')
    assets_data = []
    for n in assetor.allNames():
        assets_data.append({'name': n, 'url': assetor[n]})
    data['assets'] = assets_data

    with_menu_context(data)
    return render_template('edit_page.html', **data)

