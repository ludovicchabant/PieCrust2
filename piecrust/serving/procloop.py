import os
import os.path
import time
import json
import queue
import logging
import itertools
import threading
from piecrust import CONFIG_PATH, THEME_CONFIG_PATH
from piecrust.chefutil import format_timed_scope
from piecrust.pipelines.base import (
    PipelineJobCreateContext, PipelineJobRunContext, PipelineJobResult,
    PipelineManager)
from piecrust.pipelines.records import (
    MultiRecord, MultiRecordHistory)


logger = logging.getLogger(__name__)

# This flag is for cancelling all long running requests like SSEs.
server_shutdown = False


class PipelineStatusServerSentEventProducer(object):
    """ The producer for Server-Sent Events (SSE) notifying the front-end
        about useful things like assets having been re-processed in the
        background.
        Each has its own queue because the user could have multiple pages
        open, each having to display notifications coming from the server.
    """
    def __init__(self, proc_loop):
        self._proc_loop = proc_loop
        self._queue = queue.Queue()
        self._start_time = 0
        self._poll_interval = 0.5
        self._ping_interval = 30
        self._time_between_pings = 0
        self._running = 0

    def addBuildEvent(self, item):
        self._queue.put_nowait(item)

    def run(self):
        logger.debug("Starting pipeline status SSE.")
        self._proc_loop.addObserver(self)
        self._start_time = time.time()
        self._running = 1

        outstr = 'event: ping\ndata: started\n\n'
        yield bytes(outstr, 'utf8')

        while self._running == 1 and not server_shutdown:
            try:
                # We use a short poll interval (less than a second) because
                # we need to catch `server_shutdown` going `True` as soon as
                # possible to exit this thread when the user hits `CTRL+C`.
                data = self._queue.get(True, self._poll_interval)
            except queue.Empty:
                # Not exact timing but close enough.
                self._time_between_pings += self._poll_interval
                if self._time_between_pings >= self._ping_interval:
                    self._time_between_pings = 0
                    logger.debug("Sending ping/heartbeat event.")
                    outstr = 'event: ping\ndata: 1\n\n'
                    yield bytes(outstr, 'utf8')
                continue

            logger.debug("Sending pipeline status SSE.")
            outstr = (('event: %s\n' % data['type']) +
                      ('id: %s\n' % data['id']) +
                      ('data: %s\n\n' % json.dumps(data)))
            self._queue.task_done()
            yield bytes(outstr, 'utf8')

    def close(self):
        logger.debug("Closing pipeline status SSE.")
        self._proc_loop.removeObserver(self)
        self._running = 2


class _AssetProcessingInfo:
    def __init__(self, source):
        self.source = source
        self.paths = set()
        self.last_bake_time = time.time()


class ProcessingLoop(threading.Thread):
    def __init__(self, appfactory, out_dir):
        super().__init__(name='pipeline-reloader', daemon=True)
        self.appfactory = appfactory
        self.out_dir = out_dir
        self.last_status_id = 0
        self.interval = 1
        self._app = None
        self._proc_infos = None
        self._last_records = None
        self._last_config_mtime = 0
        self._obs = []
        self._obs_lock = threading.Lock()
        config_name = (
            THEME_CONFIG_PATH if appfactory.theme_site else CONFIG_PATH)
        self._config_path = os.path.join(appfactory.root_dir, config_name)

    def addObserver(self, obs):
        with self._obs_lock:
            self._obs.append(obs)

    def removeObserver(self, obs):
        with self._obs_lock:
            self._obs.remove(obs)

    def run(self):
        logger.debug("Initializing processing loop with output: %s" %
                     self.out_dir)
        try:
            self._init()
        except Exception as ex:
            logger.error("Error initializing processing loop:")
            logger.exception(ex)
            return

        logger.debug("Doing initial processing loop bake...")
        self._runPipelinesSafe()

        logger.debug("Running processing loop...")
        self._last_config_mtime = os.path.getmtime(self._config_path)

        while True:
            cur_config_time = os.path.getmtime(self._config_path)
            if self._last_config_mtime < cur_config_time:
                logger.info("Site configuration changed, reloading pipeline.")
                self._last_config_mtime = cur_config_time
                self._init()
                self._runPipelines()
                continue

            for procinfo in self._proc_infos.values():
                # For each assets folder we try to find the first new or
                # modified file. If any, we just run the pipeline on
                # that source.
                found_new_or_modified = False
                for item in procinfo.source.getAllContents():
                    path = item.spec
                    if path not in procinfo.paths:
                        logger.debug("Found new asset: %s" % path)
                        procinfo.paths.add(path)
                        found_new_or_modified = True
                        break
                    if os.path.getmtime(path) > procinfo.last_bake_time:
                        logger.debug("Found modified asset: %s" % path)
                        found_new_or_modified = True
                        break
                if found_new_or_modified:
                    with format_timed_scope(
                            logger,
                            "change detected, reprocessed '%s'." %
                            procinfo.source.name):
                        self._runPipelinesSafe(procinfo.source)

            time.sleep(self.interval)

    def _init(self):
        self._app = self.appfactory.create()
        self._last_records = MultiRecord()

        self._proc_infos = {}
        for src in self._app.sources:
            if src.config['pipeline'] != 'asset':
                continue

            procinfo = _AssetProcessingInfo(src)
            self._proc_infos[src.name] = procinfo

            # Build the list of initial asset files.
            for item in src.getAllContents():
                procinfo.paths.add(item.spec)

    def _runPipelinesSafe(self, only_for_source=None):
        try:
            self._runPipelines(only_for_source)
        except Exception as ex:
            logger.error("Error while running asset pipeline:")
            logger.exception(ex)

    def _runPipelines(self, only_for_source):
        from piecrust.baking.baker import Baker

        allowed_sources = None
        if only_for_source:
            allowed_sources = [only_for_source.name]
        baker = Baker(
            self.appfactory, self._app, self.out_dir,
            allowed_pipelines=['asset'],
            allowed_sources=allowed_sources,
            rotate_bake_records=False)
        records = baker.bake()

        self._onPipelinesRun(records)

    def _onPipelinesRun(self, records):
        self.last_status_id += 1

        if records.success:
            for rec in records.records:
                changed = filter(
                    lambda i: not i.was_collapsed_from_last_run,
                    rec.getEntries())
                changed = itertools.chain.from_iterable(
                    map(lambda i: i.out_paths, changed))
                changed = list(changed)
                item = {
                    'id': self.last_status_id,
                    'type': 'pipeline_success',
                    'assets': changed}

                self._notifyObservers(item)
        else:
            item = {
                'id': self.last_status_id,
                'type': 'pipeline_error',
                'assets': []}
            for rec in records.records:
                for entry in rec.getEntries():
                    if entry.errors:
                        asset_item = {
                            'path': entry.item_spec,
                            'errors': list(entry.errors)}
                        item['assets'].append(asset_item)

                self._notifyObservers(item)

    def _notifyObservers(self, item):
        with self._obs_lock:
            observers = list(self._obs)
        for obs in observers:
            obs.addBuildEvent(item)

