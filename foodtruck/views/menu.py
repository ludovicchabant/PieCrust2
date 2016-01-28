from flask import g, request, url_for
from flask.ext.login import current_user


def get_menu_context():
    entries = []
    entries.append({
        'url': '/',
        'title': "Dashboard",
        'icon': 'speedometer'})

    site = g.sites.get().piecrust_app
    for s in site.sources:
        if s.is_theme_source:
            continue

        source_icon = s.config.get('admin_icon', 'document')
        if s.name == 'pages':
            source_icon = 'document-text'
        elif 'blog' in s.name:
            source_icon = 'filing'

        url_write = url_for('write_page', source_name=s.name)
        url_listall = url_for('list_source', source_name=s.name)

        ctx = {
                'url': url_listall,
                'title': s.name,
                'icon': source_icon,
                'entries': [
                    {'url': url_listall, 'title': "List All"},
                    {'url': url_write, 'title': "Write New"}
                    ]
                }
        entries.append(ctx)

    entries.append({
        'url': url_for('publish'),
        'title': "Publish",
        'icon': 'upload'})

    # entries.append({
    #     'url': url_for('settings'),
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
            'url_logout': url_for('logout')}
    return data


