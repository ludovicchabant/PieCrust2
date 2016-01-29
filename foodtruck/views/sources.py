from flask import g, abort, render_template, url_for
from flask.ext.login import login_required
from piecrust.data.paginator import Paginator
from ..textutil import text_preview, html_to_text
from ..views import with_menu_context
from ..web import app


@app.route('/list/<source_name>/', defaults={'page_num': 1})
@app.route('/list/<source_name>/<int:page_num>')
@login_required
def list_source(source_name, page_num):
    site = g.site.piecrust_app
    source = site.getSource(source_name)
    if source is None:
        abort(400)

    i = 0
    data = {'title': "List %s" % source_name}
    data['pages'] = []
    pgn = Paginator(None, source, page_num=page_num, items_per_page=20)
    for p in pgn.items:
        page_data = {
                'title': p['title'],
                'slug': p['slug'],
                'source': source_name,
                'url': url_for('edit_page', slug=p['slug']),
                'text': text_preview(html_to_text(p['content']), length=300)}
        data['pages'].append(page_data)

    prev_page_url = None
    if pgn.prev_page_number:
        prev_page_url = url_for(
                'list_source', source_name=source_name,
                page_num=pgn.prev_page_number)
    next_page_url = None
    if pgn.next_page_number:
        next_page_url = url_for(
                'list_source', source_name=source_name,
                page_num=pgn.next_page_number)

    page_urls = []
    for i in pgn.all_page_numbers(7):
        url = None
        if i != page_num:
            url = url_for('list_source', source_name=source_name, page_num=i)
        page_urls.append({'num': i, 'url': url})

    data['pagination'] = {
            'prev_page': prev_page_url,
            'next_page': next_page_url,
            'nums': page_urls
            }

    with_menu_context(data)
    return render_template('list_source.html', **data)

