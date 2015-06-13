import os.path
import mock
from piecrust.app import PieCrust, PieCrustConfiguration
from piecrust.page import Page
from piecrust.rendering import QualifiedPage, PageRenderingContext, render_page


def get_mock_app(config=None):
    app = mock.MagicMock(spec=PieCrust)
    app.config = PieCrustConfiguration()
    return app


def get_simple_page(app, rel_path):
    source = app.getSource('pages')
    metadata = {'slug': os.path.splitext(rel_path)[0]}
    return Page(source, metadata, rel_path)


def render_simple_page(page, route, route_metadata):
    qp = QualifiedPage(page, route, route_metadata)
    ctx = PageRenderingContext(qp)
    rp = render_page(ctx)
    return rp.content


from .tmpfs import (
        TempDirFileSystem as mock_fs,
        TempDirScope as mock_fs_scope)

