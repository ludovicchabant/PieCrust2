import os
import os.path
import time
import errno
import signal
import logging
from .blueprint import foodtruck_bp


logger = logging.getLogger(__name__)

server_shutdown = False


def _shutdown_server_and_raise_sigint(is_app_debug):
    if (not is_app_debug or
            os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
        # This is needed when hitting CTRL+C to shutdown the Werkzeug server,
        # otherwise SSE generators will keep it alive.
        logger.debug("Shutting down SSE generators...")
        for h in logger.handlers:
            h.flush()
        global server_shutdown
        server_shutdown = True
    raise KeyboardInterrupt()


def record_pipeline(state):
    if state.app.config.get('FOODTRUCK_CMDLINE_MODE', False):
        # Make sure CTRL+C works correctly.
        logger.debug("Adding SIGINT callback for pipeline thread.")
        signal.signal(
            signal.SIGINT,
            lambda *args: _shutdown_server_and_raise_sigint(
                state.app.debug))


foodtruck_bp.record(record_pipeline)


def _read_pid_file(pid_file):
    logger.debug("Reading PID file: %s" % pid_file)
    try:
        with open(pid_file, 'r') as fp:
            pid_str = fp.read()

        return int(pid_str.strip())
    except Exception:
        logger.error("Error reading PID file.")
        raise


def _pid_exists(pid):
    logger.debug("Checking if process ID %d is running" % pid)
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


class PublishLogReader(object):
    _poll_interval = 1        # Check the process every 1 seconds.
    _ping_interval = 30       # Send a ping message every 30 seconds.

    def __init__(self, pid_path, log_path):
        self.pid_path = pid_path
        self.log_path = log_path

    def run(self):
        logger.debug("Opening publish log...")
        pid = None
        pid_mtime = 0
        is_running = False
        last_seek = -1
        last_ping_time = 0
        try:
            while not server_shutdown:
                # PING!
                interval = time.time() - last_ping_time
                if interval > self._ping_interval:
                    logger.debug("Sending ping...")
                    last_ping_time = time.time()
                    yield bytes("event: ping\ndata: 1\n\n", 'utf8')

                # Check the PID file timestamp.
                try:
                    new_mtime = os.path.getmtime(self.pid_path)
                except OSError:
                    new_mtime = 0

                # If there's a valid PID file and we either just started
                # streaming (pid_mtime == 0) or we remember an older version
                # of that PID file (pid_mtime != new_mtime), let's read the
                # PID from the file.
                is_pid_file_prehistoric = False
                if new_mtime > 0 and new_mtime != pid_mtime:
                    is_pid_file_prehistoric = (pid_mtime == 0)
                    pid_mtime = new_mtime
                    pid = _read_pid_file(self.pid_path)

                if is_pid_file_prehistoric:
                    logger.debug("PID file is pre-historic, we will skip the "
                                 "first parts of the log.")

                # If we have a valid PID, let's check if the process is
                # currently running.
                was_running = is_running
                if pid:
                    is_running = _pid_exists(pid)
                    logger.debug(
                        "Process %d is %s" %
                        (pid, 'running' if is_running else 'not running'))
                    if not is_running:
                        # Let's forget this PID file until it changes.
                        pid = None
                else:
                    is_running = False

                # Read new data from the log file.
                new_data = None
                if is_running or was_running:
                    if last_seek < 0:
                        # Only send the "publish started" message if we
                        # actually caught the process as it was starting, not
                        # if we started streaming after it started.
                        # This means we saw the PID file get changed.
                        if not is_pid_file_prehistoric:
                            outstr = (
                                'event: message\n'
                                'data: Publish started.\n\n')
                            yield bytes(outstr, 'utf8')
                        last_seek = 0

                    try:
                        with open(self.log_path, 'r', encoding='utf8') as fp:
                            fp.seek(last_seek)
                            new_data = fp.read()
                            last_seek = fp.tell()
                    except OSError:
                        pass
                if not is_running:
                    # Process is not running anymore, let's reset our seek
                    # marker back to the beginning.
                    last_seek = -1

                # Stream the new data to the client, but don't send old stuff
                # that happened before we started this stream.
                if new_data and not is_pid_file_prehistoric:
                    logger.debug("SSE: %s" % new_data)
                    for line in new_data.split('\n'):
                        outstr = 'event: message\ndata: %s\n\n' % line
                        yield bytes(outstr, 'utf8')

                time.sleep(self._poll_interval)

        except GeneratorExit:
            pass

        logger.debug("Closing publish log...")

