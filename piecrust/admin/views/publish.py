import copy
import logging
from flask import request, g, url_for, render_template, Response
from flask.ext.login import login_required
from ..blueprint import foodtruck_bp
from ..pubutil import PublishLogReader
from ..views import with_menu_context


logger = logging.getLogger(__name__)


@foodtruck_bp.route('/publish', methods=['GET', 'POST'])
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
        data = {'error': "There are no publish targets defined in your "
                         "configuration file."}
        return render_template('error.html', **data)

    try:
        with open(site.publish_log_file, 'r') as fp:
            last_pub_log = fp.read()
    except OSError:
        last_pub_log = None

    data = {}
    data['url_run'] = url_for('.publish')
    data['site_title'] = site.piecrust_app.config.get('site/title',
                                                      "Unnamed Website")
    data['targets'] = []
    for tn in sorted(pub_cfg.keys()):
        tc = pub_cfg[tn]
        desc = None
        if isinstance(tc, dict):
            desc = tc.get('description')
        data['targets'].append({
            'name': tn,
            'description': desc
        })

    data['last_log'] = last_pub_log

    with_menu_context(data)

    return render_template('publish.html', **data)


@foodtruck_bp.route('/publish-log')
@login_required
def stream_publish_log():
    pid_path = g.site.publish_pid_file
    log_path = g.site.publish_log_file
    rdr = PublishLogReader(pid_path, log_path)

    response = Response(rdr.run(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    return response

