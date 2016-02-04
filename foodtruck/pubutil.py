import os
import os.path
import time
import errno
import signal
import logging
from .web import app


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


if app.config['FOODTRUCK_CMDLINE_MODE']:
    # Make sure CTRL+C works correctly.
    signal.signal(signal.SIGINT,
                  lambda *args: _shutdown_server_and_raise_sigint())


def _pid_exists(pid):
    try:
        os.kill(pid, 0)
    except OSError as ex:
        if ex.errno == errno.ESRCH:
            # No such process.
            return False
        elif ex.errno == errno.EPERM:
            # No permission, so process exists.
            return True
        else:
            raise
    else:
        return True


def _read_pid_file(pid_file):
    logger.debug("Reading PID file: %s" % pid_file)
    try:
        with open(pid_file, 'r') as fp:
            pid_str = fp.read()

        return int(pid_str.strip())
    except Exception:
        logger.error("Error reading PID file.")
        raise


class PublishLogReader(object):
    _pub_max_time = 10 * 60   # Don't bother about pubs older than 10mins.
    _poll_interval = 1        # Check the process every 1 seconds.
    _ping_interval = 30       # Send a ping message every 30 seconds.

    def __init__(self, pid_path, log_path):
        self.pid_path = pid_path
        self.log_path = log_path
        self._pub_pid_mtime = 0
        self._last_seek = -1
        self._last_ping_time = 0

    def run(self):
        logger.debug("Opening publish log...")
        pid = None
        is_running = False
        try:
            while not server_shutdown:
                # PING!
                interval = time.time() - self._last_ping_time
                if interval > self._ping_interval:
                    logger.debug("Sending ping...")
                    self._last_ping_time = time.time()
                    yield bytes("event: ping\ndata: 1\n\n", 'utf8')

                # Check if the PID file has changed.
                try:
                    new_mtime = os.path.getmtime(self.pid_path)
                except OSError:
                    new_mtime = 0

                if (new_mtime > 0 and
                        time.time() - new_mtime > self._pub_max_time):
                    new_mtime = 0

                # Re-read the PID file.
                prev_mtime = self._pub_pid_mtime
                if new_mtime > 0 and new_mtime != prev_mtime:
                    self._pub_pid_mtime = new_mtime
                    pid = _read_pid_file(self.pid_path)
                    if pid:
                        logger.debug("Monitoring new process, PID: %d" % pid)

                was_running = is_running
                if pid:
                    is_running = _pid_exists(pid)
                    logger.debug(
                            "Process %d is %s" %
                            (pid, 'running' if is_running else 'not running'))
                    if not is_running:
                        pid = None
                else:
                    is_running = False

                # Send data.
                new_data = None
                if is_running or was_running:
                    if self._last_seek < 0:
                        outstr = 'event: message\ndata: Publish started.\n\n'
                        yield bytes(outstr, 'utf8')
                        self._last_seek = 0

                    try:
                        with open(self.log_path, 'r', encoding='utf8') as fp:
                            fp.seek(self._last_seek)
                            new_data = fp.read()
                            self._last_seek = fp.tell()
                    except OSError:
                        pass
                if not is_running:
                    self._last_seek = 0

                if new_data:
                    logger.debug("SSE: %s" % new_data)
                    for line in new_data.split('\n'):
                        outstr = 'event: message\ndata: %s\n\n' % line
                        yield bytes(outstr, 'utf8')

                time.sleep(self._poll_interval)

        except GeneratorExit:
            pass

        logger.debug("Closing publish log...")

