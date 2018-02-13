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
from piecrust.pipelines.records import MultiRecord


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


class ProcessingLoopBase:
    def __init__(self, appfactory, out_dir):
        self.appfactory = appfactory
        self.out_dir = out_dir
        self.last_status_id = 0
        self._app = None
        self._obs = []
        self._obs_lock = threading.Lock()
        config_name = (
            THEME_CONFIG_PATH if appfactory.theme_site else CONFIG_PATH)
        self.config_path = os.path.join(appfactory.root_dir, config_name)

    def addObserver(self, obs):
        with self._obs_lock:
            self._obs.append(obs)

    def removeObserver(self, obs):
        with self._obs_lock:
            self._obs.remove(obs)

    def getApp(self):
        return self._app

    def initialize(self):
        self._app = self.appfactory.create()
        self.onInitialize()

    def onInitialize(self):
        pass

    def start(self):
        logger.info("Starting processing loop with output: %s" %
                    self.out_dir)
        try:
            self.initialize()
        except Exception as ex:
            logger.error("Error initializing processing loop:")
            logger.exception(ex)
            return

        logger.debug("Doing initial processing loop bake...")
        self.runPipelines()

        self.onStart()

    def onStart(self):
        raise NotImplementedError()

    def getSources(self):
        for src in self._app.sources:
            if src.config.get('pipeline') != 'asset':
                continue
            yield src

    def runPipelines(self, only_for_source=None):
        try:
            self._doRunPipelines(only_for_source)
        except Exception as ex:
            logger.error("Error while running asset pipeline:")
            logger.exception(ex)

    def _doRunPipelines(self, only_for_source):
        from piecrust.baking.baker import Baker

        allowed_sources = None
        if only_for_source:
            allowed_sources = [only_for_source.name]
        baker = Baker(
            self.appfactory, self._app, self.out_dir,
            allowed_pipelines=['asset'],
            allowed_sources=allowed_sources,
            rotate_bake_records=False,
            keep_unused_records=(allowed_sources is not None))
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


try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _has_watchdog = True
except ImportError:
    _has_watchdog = False


if _has_watchdog:
    class _AssetFileEventHandler(FileSystemEventHandler):
        def __init__(self, proc_loop, source):
            self._proc_loop = proc_loop
            self._source = source

        def on_any_event(self, event):
            if event.is_directory:
                return

            pl = self._proc_loop
            with pl._lock:
                pl._ops.append({
                    'op': 'bake',
                    'source': self._source,
                    'path': event.src_path,
                    'change': event.event_type,
                    'time': time.time()})
                pl._event.set()


    class _SiteConfigEventHandler(FileSystemEventHandler):
        def __init__(self, proc_loop, path):
            self._proc_loop = proc_loop
            self._path = path

        def on_modified(self, event):
            if event.src_path != self._path:
                return

            pl = self._proc_loop
            with pl._lock:
                pl._ops.append({'op': 'reinit', 'time': time.time()})
                pl._event.set()


    class WatchdogProcessingLoop(ProcessingLoopBase):
        def __init__(self, appfactory, out_dir):
            ProcessingLoopBase.__init__(self, appfactory, out_dir)
            self._op_thread = threading.Thread(
                name='watchdog-operations',
                target=self._runOpThread,
                daemon=True)
            self._lock = threading.Lock()
            self._event = threading.Event()
            self._ops = []
            self._last_op_time = 0

        def onStart(self):
            logger.debug("Running watchdog monitor on:")
            observer = Observer()

            event_handler = _SiteConfigEventHandler(self, self.config_path)
            observer.schedule(event_handler, os.path.dirname(self.config_path))
            logger.debug(" - %s" % self.config_path)

            for src in self.getSources():
                path = getattr(src, 'fs_endpoint_path', None)
                if not path:
                    logger.warn("Skipping source '%s' -- it doesn't have "
                                "a file-system endpoint." % src.name)
                    continue
                if not os.path.isdir(path):
                    continue

                logger.debug(" - %s" % path)
                event_handler = _AssetFileEventHandler(self, src)
                observer.schedule(event_handler, path, recursive=True)

            observer.start()
            self._op_thread.start()

        def _runOpThread(self):
            while not server_shutdown:
                try:
                    self._event.wait()
                    with self._lock:
                        ops = self._ops
                        self._ops = []
                        self._event.clear()

                    orig_len = len(ops)
                    lot = self._last_op_time
                    ops = list(filter(lambda o: o['time'] > lot, ops))
                    logger.debug("Got %d ops, with %d that happened after "
                                 "our last operation." % (orig_len, len(ops)))
                    if len(ops) == 0:
                        continue

                    if any(filter(lambda o: o['op'] == 'reinit', ops)):
                        logger.info("Site configuration changed, "
                                    "reloading pipeline.")
                        self.initialize()
                        self.runPipelines()
                        continue

                    sources = set()
                    ops = list(filter(lambda o: o['op'] == 'bake', ops))
                    for op in ops:
                        logger.info("Detected file-system change: "
                                    "%s [%s]" %
                                    (op['path'], op['change']))
                        sources.add(op['source'])

                    logger.debug("Processing: %s" % [s.name for s in sources])
                    for s in sources:
                        self.runPipelines(s)

                    self._last_op_time = time.time()

                except (KeyboardInterrupt, SystemExit):
                    break

    ProcessingLoop = WatchdogProcessingLoop

else:
    class LegacyProcessingLoop(ProcessingLoopBase, threading.Thread):
        def __init__(self, appfactory, out_dir):
            ProcessingLoopBase.__init__(self, appfactory, out_dir)
            threading.Thread.__init__(self, name='pipeline-reloader',
                                      daemon=True)
            self.interval = 1
            self._proc_infos = None
            self._last_config_mtime = 0

        def onInitialize(self):
            self._proc_infos = {}
            for src in self.getSources():
                procinfo = _AssetProcessingInfo(src)
                self._proc_infos[src.name] = procinfo

                # Build the list of initial asset files.
                for item in src.getAllContents():
                    procinfo.paths.add(item.spec)

        def onStart(self):
            self._last_config_mtime = os.path.getmtime(self.config_path)
            threading.Thread.start(self)

        def run(self):
            while True:
                cur_config_time = os.path.getmtime(self.config_path)
                if self._last_config_mtime < cur_config_time:
                    logger.info("Site configuration changed, reloading pipeline.")
                    self._last_config_mtime = cur_config_time
                    self.initialize()
                    self.runPipelines()
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
                        logger.info("change detected, reprocessed '%s'." %
                                    procinfo.source.name)
                        self.runPipelines(procinfo.source)
                        procinfo.last_bake_time = time.time()

                time.sleep(self.interval)

    ProcessingLoop = LegacyProcessingLoop
