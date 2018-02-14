from flask import g, request, url_for
from flask.ext.login import current_user
from piecrust.sources.interfaces import IInteractiveSource


def get_menu_context():
    entries = []
    entries.append({
        'url': url_for('FoodTruck.index'),
        'title': "Dashboard",
        'icon': 'dashboard'})

    site = g.site.piecrust_app
    for source in site.sources:
        if source.is_theme_source:
            continue
        if not isinstance(source, IInteractiveSource):
            continue

        # Figure out the icon to use... we do some hard-coded stuff to
        # have something vaguely pretty out of the box.
        source_icon = source.config.get('admin_icon')
        if source_icon is None:
            if source.name == 'pages':
                source_icon = 'document'
            elif 'blog' in source.name or 'posts' in source.name:
                source_icon = 'box'
            else:
                source_icon = 'file'

        url_write = url_for('.write_page', source_name=source.name)
        url_listall = url_for('.list_source', source_name=source.name)

        ctx = {
            'url': url_listall,
            'title': source.name,
            'icon': source_icon,
            'quicklink': {
                'icon': 'plus',
                'url': url_write,
                'title': "Write New"
            },
            'entries': [
                {'url': url_listall, 'title': "List All"},
                {'url': url_write, 'title': "Write New"}
            ]
        }
        entries.append(ctx)

    entries.append({
        'url': url_for('.publish'),
        'title': "Publish",
        'icon': 'cloud-upload'})

    # TODO: re-enable settings UI at some point.
    # entries.append({
    #     'url': url_for('.settings'),
    #     'title': "Settings",
    #     'icon': 'gear-b'})

    for e in entries:
        needs_more_break = False
        if 'entries' in e:
            for e2 in e['entries']:
                if e2['url'] == request.path:
                    e['open'] = True
                    e2['active'] = True
                    needs_more_break = True
                    break
        if needs_more_break:
            break

        if e['url'] == request.path:
            e['active'] = True
            break

    data = {'entries': entries,
            'user': current_user,
            'url_logout': url_for('.logout')}
    return data


