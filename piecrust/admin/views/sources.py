import re
from flask import g, abort, render_template, url_for
from flask.ext.login import login_required
from piecrust.data.paginator import Paginator
from ..blueprint import foodtruck_bp
from ..views import with_menu_context


@foodtruck_bp.route('/list/<source_name>/', defaults={'page_num': 1})
@foodtruck_bp.route('/list/<source_name>/<int:page_num>')
@login_required
def list_source(source_name, page_num):
    site = g.site.piecrust_app
    source = site.getSource(source_name)
    if source is None:
        abort(400)

    i = 0
    default_author = site.config.get('site/author')
    data = {'title': "List %s" % source_name}
    data['pages'] = []
    pgn = Paginator(source, None, sub_num=page_num, items_per_page=20)
    for p in pgn.items:
        page_data = {
            'title': p.get('title') or _get_first_line_title(p),
            'author': p.get('author') or default_author,
            'timestamp': p.get('timestamp'),
            'tags': p.get('tags', []),
            'category': p.get('category'),
            'source': source_name,
            'url': url_for('.edit_page', url=p['rel_url'])
        }
        data['pages'].append(page_data)

    prev_page_url = None
    if pgn.prev_page_number:
        prev_page_url = url_for(
            '.list_source', source_name=source_name,
            page_num=pgn.prev_page_number)
    next_page_url = None
    if pgn.next_page_number:
        next_page_url = url_for(
            '.list_source', source_name=source_name,
            page_num=pgn.next_page_number)

    page_urls = []
    for i in pgn.all_page_numbers(7):
        url = None
        if i != page_num:
            url = url_for('.list_source', source_name=source_name, page_num=i)
        page_urls.append({'num': i, 'url': url})

    data['pagination'] = {
        'prev_page': prev_page_url,
        'next_page': next_page_url,
        'nums': page_urls
    }

    with_menu_context(data)
    return render_template('list_source.html', **data)


re_first_line_title = re.compile(r'[\n\r\.\!\?;]')


def _get_first_line_title(pagedata):
    content = pagedata.get('raw_content') or ''
    content = content.content.strip()
    if not content:
        return '<empty page>'

    m = re_first_line_title.search(content, 1)
    if m:
        content = content[:m.start()]

    words = content.split(' ')
    title = words[0]
    cur_word_idx = 1
    while len(title) < 60 and cur_word_idx < len(words):
        title += ' ' + words[cur_word_idx]
        cur_word_idx += 1

    return content
