import os
import time
import os.path
import logging
from piecrust.chefutil import format_timed
from piecrust.processing.base import FORCE_BUILD


logger = logging.getLogger(__name__)


STATE_UNKNOWN = 0
STATE_DIRTY = 1
STATE_CLEAN = 2


class ProcessingTreeError(Exception):
    pass


class ProcessorNotFoundError(ProcessingTreeError):
    pass


class ProcessorError(ProcessingTreeError):
    def __init__(self, proc_name, in_path, *args):
        super(ProcessorError, self).__init__(*args)
        self.proc_name = proc_name
        self.in_path = in_path

    def __str__(self):
        return "Processor %s failed on: %s" % (self.proc_name, self.in_path)


class ProcessingTreeNode(object):
    def __init__(self, path, available_procs, level=0):
        self.path = path
        self.available_procs = available_procs
        self.outputs = []
        self.level = level
        self.state = STATE_UNKNOWN
        self._processor = None

    def getProcessor(self):
        if self._processor is None:
            for p in self.available_procs:
                if p.matches(self.path):
                    self._processor = p
                    self.available_procs.remove(p)
                    break
            else:
                raise ProcessorNotFoundError()
        return self._processor

    def setState(self, state, recursive=True):
        self.state = state
        if recursive:
            for o in self.outputs:
                o.setState(state, True)

    @property
    def is_leaf(self):
        return len(self.outputs) == 0

    def getLeaves(self):
        if self.is_leaf:
            return [self]
        leaves = []
        for o in self.outputs:
            for l in o.getLeaves():
                leaves.append(l)
        return leaves


class ProcessingTreeBuilder(object):
    def __init__(self, processors):
        self.processors = processors

    def build(self, path):
        tree_root = ProcessingTreeNode(path, list(self.processors))

        loop_guard = 100
        walk_stack = [tree_root]
        while len(walk_stack) > 0:
            loop_guard -= 1
            if loop_guard <= 0:
                raise ProcessingTreeError("Infinite loop detected!")

            cur_node = walk_stack.pop()
            proc = cur_node.getProcessor()

            # If the root tree node (and only that one) wants to bypass this
            # whole tree business, so be it.
            if proc.is_bypassing_structured_processing:
                if cur_node != tree_root:
                    raise ProcessingTreeError("Only root processors can "
                                              "bypass structured processing.")
                break

            # Get the destination directory and output files.
            rel_dir, basename = os.path.split(cur_node.path)
            out_names = proc.getOutputFilenames(basename)
            if out_names is None:
                continue

            for n in out_names:
                out_node = ProcessingTreeNode(
                    os.path.join(rel_dir, n),
                    list(cur_node.available_procs),
                    cur_node.level + 1)
                cur_node.outputs.append(out_node)

                if proc.PROCESSOR_NAME != 'copy':
                    walk_stack.append(out_node)

        return tree_root


class ProcessingTreeRunner(object):
    def __init__(self, base_dir, tmp_dir, out_dir):
        self.base_dir = base_dir
        self.tmp_dir = tmp_dir
        self.out_dir = out_dir

    def processSubTree(self, tree_root):
        did_process = False
        walk_stack = [tree_root]
        while len(walk_stack) > 0:
            cur_node = walk_stack.pop()

            self._computeNodeState(cur_node)
            if cur_node.state == STATE_DIRTY:
                did_process_this_node = self.processNode(cur_node)
                did_process |= did_process_this_node

                if did_process_this_node:
                    for o in cur_node.outputs:
                        if not o.is_leaf:
                            walk_stack.append(o)
            else:
                for o in cur_node.outputs:
                    if not o.is_leaf:
                        walk_stack.append(o)
        return did_process

    def processNode(self, node):
        full_path = self._getNodePath(node)
        proc = node.getProcessor()
        if proc.is_bypassing_structured_processing:
            try:
                start_time = time.perf_counter()
                with proc.app.env.stats.timerScope(proc.__class__.__name__):
                    proc.process(full_path, self.out_dir)
                print_node(
                    node,
                    format_timed(
                        start_time, "(bypassing structured processing)",
                        colored=False))
                return True
            except Exception as e:
                raise ProcessorError(proc.PROCESSOR_NAME, full_path) from e

        # All outputs of a node must go to the same directory, so we can get
        # the output directory off of the first output.
        base_out_dir = self._getNodeBaseDir(node.outputs[0])
        rel_out_dir = os.path.dirname(node.path)
        out_dir = os.path.join(base_out_dir, rel_out_dir)
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir, 0o755, exist_ok=True)
            except OSError:
                pass

        try:
            start_time = time.perf_counter()
            with proc.app.env.stats.timerScope(proc.__class__.__name__):
                proc_res = proc.process(full_path, out_dir)
            if proc_res is None:
                raise Exception("Processor '%s' didn't return a boolean "
                                "result value." % proc)
            if proc_res:
                print_node(node, "-> %s" % out_dir)
                return True
            else:
                print_node(node, "-> %s [clean]" % out_dir)
                return False
        except Exception as e:
            raise ProcessorError(proc.PROCESSOR_NAME, full_path) from e

    def _computeNodeState(self, node):
        if node.state != STATE_UNKNOWN:
            return

        proc = node.getProcessor()
        if (proc.is_bypassing_structured_processing or
                not proc.is_delegating_dependency_check):
            # This processor wants to handle things on its own...
            node.setState(STATE_DIRTY, False)
            return

        start_time = time.perf_counter()

        # Get paths and modification times for the input path and
        # all dependencies (if any).
        base_dir = self._getNodeBaseDir(node)
        full_path = os.path.join(base_dir, node.path)
        in_mtime = (full_path, os.path.getmtime(full_path))
        force_build = False
        try:
            deps = proc.getDependencies(full_path)
            if deps == FORCE_BUILD:
                force_build = True
            elif deps is not None:
                for dep in deps:
                    dep_mtime = os.path.getmtime(dep)
                    if dep_mtime > in_mtime[1]:
                        in_mtime = (dep, dep_mtime)
        except Exception as e:
            logger.warning("%s -- Will force-bake: %s" % (e, node.path))
            node.setState(STATE_DIRTY, True)
            return

        if force_build:
            # Just do what the processor told us to do.
            node.setState(STATE_DIRTY, True)
            message = "Processor requested a forced build."
            print_node(node, message)
        else:
            # Get paths and modification times for the outputs.
            message = None
            for o in node.outputs:
                full_out_path = self._getNodePath(o)
                if not os.path.isfile(full_out_path):
                    message = "Output '%s' doesn't exist." % o.path
                    break
                o_mtime = os.path.getmtime(full_out_path)
                if o_mtime < in_mtime[1]:
                    message = "Input '%s' is newer than output '%s'." % (
                        in_mtime[0], o.path)
                    break
            if message is not None:
                node.setState(STATE_DIRTY, True)
                message += " Re-processing sub-tree."
                print_node(node, message)
            else:
                node.setState(STATE_CLEAN, False)

        if node.state == STATE_DIRTY:
            state = "dirty"
        elif node.state == STATE_CLEAN:
            state = "clean"
        else:
            state = "unknown"
        logger.debug(format_timed(start_time,
                                  "Computed node dirtyness: %s" % state,
                                  indent_level=node.level, colored=False))

    def _getNodeBaseDir(self, node):
        if node.level == 0:
            return self.base_dir
        if node.is_leaf:
            return self.out_dir
        return os.path.join(self.tmp_dir, str(node.level))

    def _getNodePath(self, node):
        base_dir = self._getNodeBaseDir(node)
        return os.path.join(base_dir, node.path)


def print_node(node, message=None, recursive=False):
    indent = '  ' * node.level
    try:
        proc_name = node.getProcessor().PROCESSOR_NAME
    except ProcessorNotFoundError:
        proc_name = 'n/a'

    message = message or ''
    logger.debug('%s%s [%s] %s' % (indent, node.path, proc_name, message))

    if recursive:
        for o in node.outputs:
            print_node(o, None, True)


def get_node_name_tree(node):
    try:
        proc_name = node.getProcessor().PROCESSOR_NAME
    except ProcessorNotFoundError:
        proc_name = 'n/a'

    children = []
    for o in node.outputs:
        if not o.outputs:
            continue
        children.append(get_node_name_tree(o))
    return (proc_name, children)

