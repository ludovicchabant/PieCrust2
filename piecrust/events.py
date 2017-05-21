
class Event(object):
    """ A simple implementation of a subscribable event.
    """
    def __init__(self):
        self._handlers = []

    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self

    def __isub__(self, handler):
        self._handlers.remove(handler)
        return self

    def fire(self, *args, **kwargs):
        # Make a copy of the handlers list in case some handler removes
        # itself while executing.
        handlers = list(self._handlers)
        for handler in handlers:
            handler(*args, **kwargs)

