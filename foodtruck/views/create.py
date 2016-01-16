import os.path
import logging
from flask import (
        g, request, abort, render_template, url_for, redirect, flash)
from flask.ext.login import login_required
from piecrust.sources.interfaces import IInteractiveSource
from piecrust.sources.base import MODE_CREATING
from piecrust.routing import create_route_metadata
from ..views import with_menu_context
from ..web import app


logger = logging.getLogger(__name__)


@app.route('/write/<source_name>', methods=['GET', 'POST'])
@login_required
def write_page(source_name):
    site = g.sites.get().piecrust_app
    source = site.getSource(source_name)
    if source is None:
        abort(400)
    if not isinstance(source, IInteractiveSource):
        abort(400)

    if request.method == 'POST':
        if 'do_save' in request.form:
            metadata = dict(request.form.items())
            form_keys = list(metadata.keys())
            for k in filter(lambda k: not k.startswith('meta-'), form_keys):
                del metadata[k]

            fac = source.findPageFactory(metadata, MODE_CREATING)
            if fac is None:
                raise Exception("Can't find page for %s" % metadata)
                abort(400)

            logger.debug("Creating page: %s" % fac.path)
            with open(fac.path, 'w', encoding='utf8') as fp:
                fp.write(request.form['page_text'])
            flash("%s was created." % os.path.relpath(fac.path, site.root_dir))

            route = site.getRoute(source.name, fac.metadata,
                                  skip_taxonomies=True)
            dummy = object()
            dummy.source_metadata = fac.metadata
            dummy.getRouteMetadata = lambda: {}
            route_metadata = create_route_metadata(dummy)
            uri = route.getUri(route_metadata)

            return redirect(url_for('edit_page', slug=uri))

        abort(400)

    return _write_page_form(source)


def _write_page_form(source):
    data = {}
    data['is_new_page'] = True
    data['source_name'] = source.name
    data['url_postback'] = url_for('write_page', source_name=source.name)
    data['fields'] = []
    for f in source.getInteractiveFields():
        data['fields'].append({
            'name': f.name,
            'display_name': f.name,
            'type': f.field_type,
            'value': f.default_value})

    with_menu_context(data)
    return render_template('create_page.html', **data)

