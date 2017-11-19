import os
import os.path
import logging
from flask import (
    current_app, g, request,
    render_template, url_for, redirect)
from flask.ext.login import login_user, logout_user, login_required
from piecrust.sources.fs import FSContentSourceBase
from piecrust.sources.interfaces import IInteractiveSource
from piecrust.uriutil import split_uri
from ..textutil import text_preview
from ..blueprint import foodtruck_bp, load_user
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

        src_data = {
            'name': source.name,
            'list_url': url_for('.list_source', source_name=source.name)}
        data['sources'].append(src_data)

        if isinstance(source, FSContentSourceBase):
            fs_endpoints[source.fs_endpoint] = source

    data['new_pages'] = []
    data['edited_pages'] = []
    data['misc_files'] = []
    if site.scm:
        st = site.scm.getStatus()
        auto_formats = site.piecrust_app.config.get('site/auto_formats',
                                                    ['html'])
        for p in st.new_files:
            pd = _getWipData(p, fs_endpoints, auto_formats, site.piecrust_app)
            if pd:
                data['new_pages'].append(pd)
            else:
                data['misc_files'].append(p)
        for p in st.edited_files:
            pd = _getWipData(p, fs_endpoints, auto_formats, site.piecrust_app)
            if pd:
                data['edited_pages'].append(pd)
            else:
                data['misc_files'].append(p)

    data['site_title'] = pcapp.config.get('site/title', "Unnamed Website")
    data['url_publish'] = url_for('.publish')
    data['url_preview'] = url_for('.preview_root_page')
    data['url_bake_assets'] = url_for('.rebake_assets')

    pub_tgts = pcapp.config.get('publish', {})
    data['publish'] = {'targets': list(pub_tgts.keys())}

    micropub = pcapp.config.get('micropub', {})
    data['publish'] = micropub.get('publish_target')

    with_menu_context(data)
    return render_template('dashboard.html', **data)


def _getWipData(path, fs_endpoints, auto_formats, pcapp):
    pathname, pathext = os.path.splitext(path)
    if pathext.lstrip('.') not in auto_formats:
        return None

    source = None
    for endpoint, s in fs_endpoints.items():
        if path.startswith(endpoint):
            source = s
            break
    if source is None:
        return None

    # TODO: this assumes FS sources, but this comes from the disk anyway.
    full_path = os.path.join(pcapp.root_dir, path)
    content_item = source.findContentFromSpec(full_path)
    if content_item is None:
        return None

    page = pcapp.getPage(source, content_item)
    uri = page.getUri()
    _, slug = split_uri(pcapp, uri)

    seg = page.getSegment()
    if not seg:
        return None

    extract = text_preview(seg.content)
    return {
        'title': page.config.get('title'),
        'slug': slug,
        'url': url_for('.edit_page', url=slug),
        'text': extract
    }


@foodtruck_bp.route('/rebake_assets', methods=['POST'])
@login_required
def rebake_assets():
    g.site.rebakeAssets()
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

