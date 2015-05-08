import os
import os.path
import time
import json
import queue
import logging
import threading


logger = logging.getLogger(__name__)


_sse_abort = threading.Event()


class PipelineStatusServerSideEventProducer(object):
    def __init__(self, status_queue):
        self.status_queue = status_queue
        self.interval = 2
        self.timeout = 60*10
        self._start_time = 0

    def run(self):
        logger.debug("Starting pipeline status SSE.")
        self._start_time = time.time()

        outstr = 'event: ping\ndata: started\n\n'
        yield bytes(outstr, 'utf8')

        count = 0
        while True:
            if time.time() > self.timeout + self._start_time:
                logger.debug("Closing pipeline status SSE, timeout reached.")
                outstr = 'event: pipeline_timeout\ndata: bye\n\n'
                yield bytes(outstr, 'utf8')
                break

            if _sse_abort.is_set():
                break

            try:
                logger.debug("Polling pipeline status queue...")
                count += 1
                data = self.status_queue.get(True, self.interval)
            except queue.Empty:
                if count < 3:
                    continue
                data = {'type': 'ping', 'message': 'ping'}
                count = 0

            event_type = data['type']
            outstr = 'event: %s\ndata: %s\n\n' % (
                    event_type, json.dumps(data))
            logger.debug("Sending pipeline status SSE.")
            yield bytes(outstr, 'utf8')

    def close(self):
        logger.debug("Closing pipeline status SSE.")


class ProcessingLoop(threading.Thread):
    def __init__(self, pipeline):
        super(ProcessingLoop, self).__init__(
                name='pipeline-reloader', daemon=True)
        self.pipeline = pipeline
        self.status_queue = queue.Queue()
        self.interval = 1
        self._paths = set()
        self._record = None
        self._last_bake = 0

    def run(self):
        # Build the first list of known files and run the pipeline once.
        app = self.pipeline.app
        roots = [os.path.join(app.root_dir, r)
                 for r in self.pipeline.mounts.keys()]
        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                self._paths |= set([os.path.join(dirpath, f)
                                    for f in filenames])
        self._last_bake = time.time()
        self._record = self.pipeline.run()

        while True:
            for root in roots:
                # For each mount root we try to find the first new or
                # modified file. If any, we just run the pipeline on
                # that mount.
                found_new_or_modified = False
                for dirpath, dirnames, filenames in os.walk(root):
                    for filename in filenames:
                        path = os.path.join(dirpath, filename)
                        if path not in self._paths:
                            logger.debug("Found new asset: %s" % path)
                            self._paths.add(path)
                            found_new_or_modified = True
                            break
                        if os.path.getmtime(path) > self._last_bake:
                            logger.debug("Found modified asset: %s" % path)
                            found_new_or_modified = True
                            break

                    if found_new_or_modified:
                        break

                if found_new_or_modified:
                    self._runPipeline(root)

            time.sleep(self.interval)

    def _runPipeline(self, root):
        self._last_bake = time.time()
        try:
            self._record = self.pipeline.run(
                    root,
                    previous_record=self._record,
                    save_record=False)

            # Update the status queue.
            # (we need to clear it because there may not be a consumer
            #  on the other side, if the user isn't running with the
            #  debug window active)
            while True:
                try:
                    self.status_queue.get_nowait()
                except queue.Empty:
                    break

            if self._record.success:
                item = {
                        'type': 'pipeline_success'}
                self.status_queue.put_nowait(item)
            else:
                item = {
                        'type': 'pipeline_error',
                        'assets': []}
                for entry in self._record.entries:
                    if entry.errors:
                        asset_item = {
                                'path': entry.rel_input,
                                'errors': list(entry.errors)}
                        item['assets'].append(asset_item)
                self.status_queue.put_nowait(item)
        except:
            pass

