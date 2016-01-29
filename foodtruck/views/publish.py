import os
import os.path
import copy
import logging
from flask import request, g, url_for, render_template, Response
from flask.ext.login import login_required
from ..pubutil import PublishLogReader
from ..views import with_menu_context
from ..web import app


logger = logging.getLogger(__name__)


@app.route('/publish', methods=['GET', 'POST'])
@login_required
def publish():
    if request.method == 'POST':
        target = request.form.get('target')
        if not target:
            raise Exception("No target specified.")

        g.site.publish(target)

    site = g.site
    pub_cfg = copy.deepcopy(site.piecrust_app.config.get('publish', {}))
    if not pub_cfg:
        data = {'error': "There are not publish targets defined in your "
                         "configuration file."}
        return render_template('error.html', **data)

    data = {}
    data['url_run'] = url_for('publish')
    data['site_title'] = site.piecrust_app.config.get('site/title', site.name)
    data['targets'] = []
    for tn in sorted(pub_cfg.keys()):
        tc = pub_cfg[tn]
        data['targets'].append({
            'name': tn,
            'description': tc.get('description'),
            'cmd': tc.get('cmd')
            })

    with_menu_context(data)

    return render_template('publish.html', **data)


@app.route('/publish-log')
@login_required
def stream_publish_log():
    site = g.site
    pid_path = os.path.join(site.root_dir, '.ft_pub.pid')
    log_path = os.path.join(site.root_dir, '.ft_pub.log')
    rdr = PublishLogReader(pid_path, log_path)

    response = Response(rdr.run(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    return response

