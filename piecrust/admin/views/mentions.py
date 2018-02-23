import logging
from flask import g, request, make_response, abort
from ..blueprint import foodtruck_bp
from piecrust.tasks.base import TaskManager


logger = logging.getLogger(__name__)


@foodtruck_bp.route('/webmention', methods=['POST'])
def post_webmention():
    # Basic validation of source/target.
    src_url = request.form.get('source')
    tgt_url = request.form.get('target')
    if not src_url or not tgt_url:
        logger.error("No source or target specified.")
        abort(400)
    if src_url.lower().rstrip('/') == tgt_url.lower().rstrip('/'):
        logger.error("Source and target are the same.")
        abort(400)

    # Create the task for handling this mention.
    pcapp = g.site.piecrust_app
    task_manager = TaskManager(pcapp)
    task_id = task_manager.createTask('mention', {
        'source': src_url,
        'target': tgt_url})

    # Either run the task now in a background process (for cheap and simple
    # setups), or leave the task there to be picked up later when someone
    # runs the task queue eventually.
    wmcfg = pcapp.config.get('webmention')
    if not wmcfg.get('use_task_queue'):
        g.site.runTask(task_id)

    return make_response("Webmention queued.", 202, [])
