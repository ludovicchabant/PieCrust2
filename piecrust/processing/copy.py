import os.path
import shutil
import logging
from piecrust.processing.base import Processor, PRIORITY_LAST


logger = logging.getLogger(__name__)


class CopyFileProcessor(Processor):
    PROCESSOR_NAME = 'copy'

    def __init__(self):
        super(CopyFileProcessor, self).__init__()
        self.priority = PRIORITY_LAST

    def matches(self, path):
        return True

    def getOutputFilenames(self, filename):
        return [filename]

    def process(self, path, out_dir):
        out_path = os.path.join(out_dir, os.path.basename(path))
        logger.debug("Copying: %s -> %s" % (path, out_path))
        shutil.copyfile(path, out_path)
        return True
