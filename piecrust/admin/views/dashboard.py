import os
import os.path
import logging
from flask import (
    current_app, g, request,
    render_template, url_for, redirect)
from flask.ext.login import login_user, logout_user, login_required
from piecrust.configuration import parse_config_header
from piecrust.sources.interfaces import IInteractiveSource
from piecrust.uriutil import split_uri
from ..textutil import text_preview
from ..blueprint import foodtruck_bp, load_user, after_this_request
from ..views import with_menu_context


logger = logging.getLogger(__name__)


@foodtruck_bp.route('/')
@login_required
def index():
    data = {}
    data['sources'] = []

    fs_endpoints = {}

    site = g.site
    pcapp = site.piecrust_app
    for source in pcapp.sources:
        if source.is_theme_source:
            continue
        if not isinstance(source, IInteractiveSource):
            continue

        items = source.getAllContents()
        src_data = {
            'name': source.name,
            'list_url': url_for('.list_source', source_name=source.name),
            'page_count': len(items)}
        data['sources'].append(src_data)

        fe = getattr(source, 'fs_endpoint', None)
        if fe:
            fs_endpoints[fe] = source

    data['new_pages'] = []
    data['edited_pages'] = []
    data['misc_files'] = []
    if site.scm:
        st = site.scm.getStatus()
        for p in st.new_files:
            pd = _getWipData(p, site, fs_endpoints)
            if pd:
                data['new_pages'].append(pd)
            else:
                data['misc_files'].append(p)
        for p in st.edited_files:
            pd = _getWipData(p, site, fs_endpoints)
            if pd:
                data['edited_pages'].append(pd)
            else:
                data['misc_files'].append(p)

    data['site_title'] = pcapp.config.get('site/title', "Unnamed Website")
    data['url_publish'] = url_for('.publish')
    data['url_preview'] = url_for('.preview_root_page')

    with_menu_context(data)
    return render_template('dashboard.html', **data)


def _getWipData(path, site, fs_endpoints):
    auto_formats = site.piecrust_app.config.get('site/auto_formats', ['html'])
    pathname, pathext = os.path.splitext(path)
    if pathext not in auto_formats:
        return None

    source = None
    for endpoint, s in fs_endpoints.items():
        if path.startswith(endpoint):
            source = s
            break
    if source is None:
        return None

    fac = source.buildPageFactory(os.path.join(site.root_dir, path))
    route = site.piecrust_app.getSourceRoute(source.name, fac.metadata)
    if not route:
        return None

    qp = QualifiedPage(fac.buildPage(), route, fac.metadata)
    uri = qp.getUri()
    _, slug = split_uri(site.piecrust_app, uri)

    with open(fac.path, 'r', encoding='utf8') as fp:
        raw_text = fp.read()

    header, offset = parse_config_header(raw_text)
    extract = text_preview(raw_text, offset=offset)
    return {
        'title': qp.config.get('title'),
        'slug': slug,
        'url': url_for('.edit_page', slug=slug),
        'text': extract
    }


@login_required
@foodtruck_bp.route('/switch_site', methods=['POST'])
def switch_site():
    site_name = request.form.get('site_name')
    if not site_name:
        return redirect(url_for('.index'))

    @after_this_request
    def _save_site(resp):
        resp.set_cookie('foodtruck_site_name', site_name)

    return redirect(url_for('.index'))


@foodtruck_bp.route('/login', methods=['GET', 'POST'])
def login():
    data = {}

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')

        user = load_user(username)
        if user is not None and current_app.bcrypt:
            if current_app.bcrypt.check_password_hash(user.password, password):
                login_user(user, remember=bool(remember))
                return redirect(url_for('.index'))
        data['message'] = (
            "User '%s' doesn't exist or password is incorrect." %
            username)

    return render_template('login.html', **data)


@foodtruck_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('.index'))

