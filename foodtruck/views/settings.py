import logging
import bcrypt
from flask import g, request, abort, render_template, redirect, url_for
from flask.ext.login import login_required
from ..views import with_menu_context
from ..web import app


logger = logging.getLogger(__name__)


def _hash_password(v):
    binpw = v.encode('utf8')
    v = bcrypt.hashpw(binpw, bcrypt.gensalt()).decode('utf8')
    return v


config_meta = {
        'scm.title': 'Source Control',
        'triggers.bake.is_shell.title': 'Use Shell'
        }

config_defaults = {
        'triggers': {
            'bake.is_shell': 'false'
            }
        }

config_coercer = {
        'security.password': _hash_password
        }


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        if '_do_save' not in request.form:
            abort(400)
        if not g.config.has(request.form['_section']):
            abort(400)

        secname = request.form['_section']

        defaults = config_defaults.get(secname)
        if defaults:
            for n, v in defaults.items():
                g.config.set('%s/%s' % (secname, n), v)

        for n, v in request.form.items():
            if n in ['_section', '_do_save']:
                continue

            coercer = config_coercer.get('%s.%s' % (secname, n))
            if coercer:
                v = coercer(v)

            logger.debug("Setting %s.%s to %s" % (secname, n, v))
            g.config.set('%s/%s' % (secname, n), v)

        g.config.save()

    data = {'sections': []}
    for secname, sec in g.config.items():
        if secname in ['DEFAULT', 'foodtruck', 'sites']:
            continue
        secdata = {}
        secdata['name'] = secname
        secdata['title'] = config_meta.get(
                '%s.title' % secname, secname.title())
        secdata['options'] = []
        for n, v in sec.items():
            opdata = {}
            opdata['name'] = n
            opdata['title'] = config_meta.get(
                    '%s.%s.title' % (secname, n), n.title())
            opdata['value'] = v
            opdata['type'] = 'text'
            if v in ['true', 'false']:
                opdata['type'] = 'checkbox'
            if secname == 'security' and n == 'password':
                opdata['type'] = 'password'
            secdata['options'].append(opdata)
        data['sections'].append(secdata)

    data['url_settings'] = url_for('settings')
    data['url_reload_settings'] = url_for('reload_settings')
    with_menu_context(data)
    return render_template('settings.html', **data)


@app.route('/reload', methods=['POST'])
@login_required
def reload_settings():
    from ..web import reload_foodtruck
    reload_foodtruck()
    return redirect(url_for('settings'))

