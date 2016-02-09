import os
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
    site = g.site.piecrust_app
    source = site.getSource(source_name)
    if source is None:
        abort(400)
    if not isinstance(source, IInteractiveSource):
        abort(400)

    if request.method == 'POST':
        if 'do_save' in request.form:
            metadata = {}
            for f in source.getInteractiveFields():
                metadata[f.name] = f.default_value
            for fk, fv in request.form.items():
                if fk.startswith('meta-'):
                    metadata[fk[5:]] = fv

            logger.debug("Searching for page with metadata: %s" % metadata)
            fac = source.findPageFactory(metadata, MODE_CREATING)
            if fac is None:
                logger.error("Can't find page for %s" % metadata)
                abort(500)

            logger.debug("Creating page: %s" % fac.path)
            os.makedirs(os.path.dirname(fac.path), exist_ok=True)
            with open(fac.path, 'w', encoding='utf8') as fp:
                fp.write('')
            flash("%s was created." % os.path.relpath(fac.path, site.root_dir))

            route = site.getRoute(source.name, fac.metadata,
                                  skip_taxonomies=True)
            if route is None:
                logger.error("Can't find route for page: %s" % fac.path)
                abort(500)

            dummy = _DummyPage(fac)
            route_metadata = create_route_metadata(dummy)
            uri = route.getUri(route_metadata)
            uri_root = '/site/%s/' % g.site.name
            uri = uri[len(uri_root):]
            logger.debug("Redirecting to: %s" % uri)

            return redirect(url_for('edit_page', slug=uri))

        abort(400)

    return _write_page_form(source)


class _DummyPage:
    def __init__(self, fac):
        self.source_metadata = fac.metadata

    def getRouteMetadata(self):
        return {}


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

