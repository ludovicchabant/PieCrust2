import os
import os.path
import shutil
import logging
from piecrust.publishing.base import Publisher


logger = logging.getLogger(__name__)


class CopyPublisher(Publisher):
    PUBLISHER_NAME = 'copy'
    PUBLISHER_SCHEME = 'file'

    def parseUrlTarget(self, url):
        self.config = {'output': (url.netloc + url.path)}

    def run(self, ctx):
        dest = self.config.get('output')

        if ctx.was_baked:
            to_upload = list(self.getBakedFiles(ctx))
            to_delete = list(self.getDeletedFiles(ctx))
            if to_upload or to_delete:
                logger.info("Copying new/changed files...")
                for path in to_upload:
                    rel_path = os.path.relpath(path, ctx.bake_out_dir)
                    dest_path = os.path.join(dest, rel_path)
                    dest_dir = os.path.dirname(dest_path)
                    os.makedirs(dest_dir, exist_ok=True)
                    try:
                        dest_mtime = os.path.getmtime(dest_path)
                    except OSError:
                        dest_mtime = 0
                    if os.path.getmtime(path) >= dest_mtime:
                        logger.info(rel_path)
                        if not ctx.preview:
                            shutil.copyfile(path, dest_path)

                logger.info("Deleting removed files...")
                for path in self.getDeletedFiles(ctx):
                    rel_path = os.path.relpath(path, ctx.bake_out_dir)
                    logger.info("%s [DELETE]" % rel_path)
                    if not ctx.preview:
                        try:
                            os.remove(path)
                        except OSError:
                            pass
            else:
                logger.info("Nothing to copy to the output folder.")

