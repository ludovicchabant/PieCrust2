import logging
from flask import (
    g, request, abort, render_template, url_for, redirect, flash)
from flask.ext.login import login_required
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

    with_menu_context(data)
    return render_template('create_page.html', **data)


def _submit_page_form(pcapp, source):
    metadata = {}
    for f in source.getInteractiveFields():
        metadata[f.name] = f.default_value
    for fk, fv in request.form.items():
        if fk.startswith('meta-'):
            metadata[fk[5:]] = fv

    logger.debug("Creating item with metadata: %s" % metadata)
    content_item = source.createContent(metadata)
    if content_item is None:
        logger.error("Can't create item for: %s" % metadata)
        abort(500)

    logger.debug("Creating content: %s" % content_item.spec)
    with source.openItem(content_item, 'w') as fp:
        fp.write('---\n')
        fp.write('draft: true\n')
        fp.write('---\n')
        fp.write('\n')
        fp.write("Start writing!\n")
    flash("'%s' was created." % content_item.spec)

    page = Page(source, content_item)
    uri = page.getUri()
    logger.debug("Redirecting to: %s" % uri)
    _, rel_url = split_uri(page.app, uri)
    return redirect(url_for('.edit_page', url=rel_url))

