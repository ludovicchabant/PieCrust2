import os
import os.path
import time
import signal
import logging
from werkzeug.wrappers import Response
from flask import g, redirect
from flask.ext.login import login_required
from ..web import app


logger = logging.getLogger(__name__)

server_shutdown = False


def _shutdown_server_and_raise_sigint():
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # This is needed when hitting CTRL+C to shutdown the Werkzeug server,
        # otherwise SSE generators will keep it alive.
        logger.debug("Shutting down SSE generators...")
        global server_shutdown
        server_shutdown = True
    raise KeyboardInterrupt()


# Make sure CTRL+C works correctly.
signal.signal(signal.SIGINT,
              lambda *args: _shutdown_server_and_raise_sigint())


class _BakeLogReader(object):
    _bake_max_time = 10 * 60  # Don't bother about bakes older than 10mins.
    _poll_interval = 2        # Check the PID file every 2 seconds.
    _ping_interval = 30       # Send a ping message every 30 seconds.

    def __init__(self, pid_path, log_path):
        self.pid_path = pid_path
        self.log_path = log_path
        self._bake_pid_mtime = 0
        self._last_seek = 0
        self._last_ping_time = 0

    def run(self):
        logger.debug("Opening bake log...")

        try:
            while not server_shutdown:
                # PING!
                interval = time.time() - self._last_ping_time
                if interval > self._ping_interval:
                    logger.debug("Sending ping...")
                    self._last_ping_time = time.time()
                    yield bytes("event: ping\ndata: 1\n\n", 'utf8')

                # Check pid file.
                prev_mtime = self._bake_pid_mtime
                try:
                    self._bake_pid_mtime = os.path.getmtime(self.pid_path)
                    if time.time() - self._bake_pid_mtime > \
                            self._bake_max_time:
                        self._bake_pid_mtime = 0
                except OSError:
                    self._bake_pid_mtime = 0

                # Send data.
                new_data = None
                if self._bake_pid_mtime > 0 or prev_mtime > 0:
                    if self._last_seek == 0:
                        outstr = 'event: message\ndata: Bake started.\n\n'
                        yield bytes(outstr, 'utf8')

                    try:
                        with open(self.log_path, 'r', encoding='utf8') as fp:
                            fp.seek(self._last_seek)
                            new_data = fp.read()
                            self._last_seek = fp.tell()
                    except OSError:
                        pass
                if self._bake_pid_mtime == 0:
                    self._last_seek = 0

                if new_data:
                    logger.debug("SSE: %s" % outstr)
                    for line in new_data.split('\n'):
                        outstr = 'event: message\ndata: %s\n\n' % line
                        yield bytes(outstr, 'utf8')

                time.sleep(self._poll_interval)

        except GeneratorExit:
            pass

        logger.debug("Closing bake log...")


@app.route('/bake', methods=['POST'])
@login_required
def bake_site():
    site = g.sites.get()
    site.bake()
    return redirect('/')


@app.route('/bakelog')
@login_required
def stream_bake_log():
    site = g.sites.get()
    pid_path = os.path.join(site.root_dir, 'foodtruck_bake.pid')
    log_path = os.path.join(site.root_dir, 'foodtruck_bake.log')
    rdr = _BakeLogReader(pid_path, log_path)

    response = Response(rdr.run(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    return response

