import os.path
import logging
from piecrust.commands.base import ChefCommand


logger = logging.getLogger(__name__)


class TasksCommand(ChefCommand):
    """ Command for managing and running task queues.
    """
    def __init__(self):
        super().__init__()
        self.name = 'tasks'
        self.description = "Manages and runs various tasks."

    def setupParser(self, parser, app):
        subparsers = parser.add_subparsers()

        p = subparsers.add_parser(
            'list',
            help="Show the list of tasks current in the queue.")
        p.set_defaults(sub_func=self._listTasks)

        p = subparsers.add_parser(
            'run',
            help="Runs the current task queue.")
        p.add_argument(
            '-k', '--keep-queue',
            action='store_true',
            help="Don't delete the task queue files.")
        p.add_argument(
            '-t', '--task',
            help="Specify which task to run.")
        p.set_defaults(sub_func=self._runTasks)

    def run(self, ctx):
        if hasattr(ctx.args, 'sub_func'):
            ctx.args.sub_func(ctx)

    def _listTasks(self, ctx):
        from piecrust.tasks.base import TaskManager

        root_dir = ctx.app.root_dir
        tm = TaskManager(ctx.app)
        tm.getTasks()
        tasks = list(tm.getTasks())
        logger.info("Task queue contains %d tasks" % len(tasks))
        for path, task_type, task_data in tasks:
            logger.info(" - [%s] %s" %
                        (task_type, os.path.relpath(path, root_dir)))

    def _runTasks(self, ctx):
        from piecrust.tasks.base import TaskManager

        only_task = ctx.args.task
        if only_task and os.path.isfile(only_task):
            only_task, _ = os.path.splitext(os.path.basename(only_task))

        tm = TaskManager(ctx.app)
        tm.runQueue(
            only_task=only_task,
            clear_queue=False)  # (not ctx.args.keep_queue))

