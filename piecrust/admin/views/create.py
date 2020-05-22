import logging
from flask import (
    g, request, abort, render_template, url_for, redirect, flash)
from flask_login import login_required
from piecrust.page import Page
from piecrust.sources.interfaces import IInteractiveSource
from piecrust.uriutil import split_uri
from ..blueprint import foodtruck_bp
from ..views import with_menu_context


logger = logging.getLogger(__name__)


@foodtruck_bp.route('/write/<source_name>', methods=['GET', 'POST'])
@login_required
def write_page(source_name):
    pcapp = g.site.piecrust_app
    source = pcapp.getSource(source_name)
    if source is None:
        abort(400)
    if not isinstance(source, IInteractiveSource):
        abort(400)

    if request.method == 'POST':
        if 'do_save' in request.form:
            return _submit_page_form(pcapp, source)
        abort(400)
    return _write_page_form(source)


def _write_page_form(source):
    data = {}
    data['is_new_page'] = True
    data['source_name'] = source.name
    data['url_postback'] = url_for('.write_page', source_name=source.name)
    data['fields'] = []
    for f in source.getInteractiveFields():
        data['fields'].append({
            'name': f.name,
            'display_name': f.name,
            'type': f.field_type,
            'value': f.default_value})

    tpl_names = []
    pcapp = g.site.piecrust_app
    for ext in pcapp.getCommandExtensions('prepare'):
        try:
            tpl_names += list(ext.getTemplateNames(pcapp))
        except AttributeError:
            pass   # For extensions that don't define `getTemplateNames`.
    data['content_templates'] = tpl_names

    with_menu_context(data)
    return render_template('create_page.html', **data)


def _submit_page_form(pcapp, source):
    metadata = {}
    for f in source.getInteractiveFields():
        metadata[f.name] = f.default_value
    for fk, fv in request.form.items():
        if fk.startswith('meta-'):
            metadata[fk[5:]] = fv

    tpl_name = request.form['content-template']

    logger.debug("Creating content with template '%s' and metadata: %s" %
                 (tpl_name, str(metadata)))
    from piecrust.commands.builtin.scaffolding import build_content
    content_item = build_content(source, metadata, tpl_name)
    flash("'%s' was created." % content_item.spec)

    page = Page(source, content_item)
    uri = page.getUri()
    logger.debug("Redirecting to: %s" % uri)
    _, rel_url = split_uri(page.app, uri)
    return redirect(url_for('.edit_page', url=rel_url))

