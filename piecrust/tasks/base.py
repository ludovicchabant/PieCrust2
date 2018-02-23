import os
import os.path
import json
import time
import logging
from piecrust.chefutil import format_timed


TASKS_DIR = '_tasks'


logger = logging.getLogger(__name__)


class TaskContext:
    def __init__(self):
        pass


class TaskRunner:
    TASK_TYPE = 'undefined'

    def __init__(self, app):
        self.app = app

    def runTask(self, task_data, ctx):
        raise NotImplementedError()


class TaskManager:
    def __init__(self, app, *, time_threshold=1):
        self.app = app
        self.time_threshold = time_threshold
        self._runners = None

    @property
    def tasks_dir(self):
        return os.path.join(self.app.root_dir, TASKS_DIR)

    def createTask(self, task_type, task_data):
        from piecrust.pathutil import ensure_dir

        tasks_dir = self.tasks_dir
        ensure_dir(tasks_dir)
        new_task = {
            'type': task_type,
            'data': task_data}
        task_id = str(int(time.time()))
        task_path = os.path.join(tasks_dir, '%s.json' % task_id)
        with open(task_path, 'w', encoding='utf8') as fp:
            json.dump(new_task, fp)
        return task_id

    def getTasks(self, *, only_task=None):
        max_time = time.time() - self.time_threshold
        tasks_dir = self.tasks_dir
        try:
            task_files = os.listdir(tasks_dir)
        except (IOError, OSError):
            task_files = []

        for tf in task_files:
            tfname, _ = os.path.splitext(tf)
            if only_task and tfname != only_task:
                continue

            tf_path = os.path.join(tasks_dir, tf)
            task_time = os.path.getmtime(tf_path)
            if task_time >= max_time:
                logger.debug("Skipping task '%s' because it's too new." % tf)
                continue

            with open(tf_path, 'r', encoding='utf8') as fp:
                task_data = json.load(fp)

            task_type = task_data.get('task')
            task_payload = task_data.get('data')
            yield (tf_path, task_type, task_payload)

    def runQueue(self, *, only_task=None, clear_queue=True):
        start_time = time.perf_counter()

        tasks = list(self.getTasks(only_task=only_task))
        for path, task_type, task_data in tasks:
            if not task_type:
                logger.error("Got task with no type: %s" % path)
                continue

            runner = self._getRunner(task_type)
            if runner is None:
                logger.error("No task runner for type: %s" % task_type)
                continue

            ctx = TaskContext()
            runner.runTask(task_data, ctx)

            if clear_queue:
                os.remove(path)

        logger.info(format_timed(
            start_time, "Ran %d tasks." % len(tasks)))

    def _getRunner(self, task_type):
        if self._runners is None:
            self._runners = {}
            for r in self.app.plugin_loader.getTaskRunners():
                self._runners[r.TASK_TYPE] = r(self.app)

        return self._runners.get(task_type)
