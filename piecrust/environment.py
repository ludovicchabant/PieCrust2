import logging
from decorators import lazy_property


logger = logging.getLogger(__name__)


class PageRepository(object):
    pass


class ExecutionContext(object):
    pass


class Environment(object):
    def __init__(self):
        self.page_repository = PageRepository()
        self._execution_ctx = None

    def initialize(self, app):
        pass

    @lazy_property
    def pages(self):
        logger.debug("Loading pages...")
        return self._loadPages()

    @lazy_property
    def posts(self):
        logger.debug("Loading posts...")
        return self._loadPosts()

    @lazy_property
    def file_system(self):
        return None

    def get_execution_context(self, auto_create=False):
        if auto_create and self._execution_ctx is None:
            self._execution_ctx = ExecutionContext()
        return self._execution_ctx

    def _loadPages(self):
        raise NotImplementedError()

    def _loadPosts(self):
        raise NotImplementedError()


class StandardEnvironment(Environment):
    pass

