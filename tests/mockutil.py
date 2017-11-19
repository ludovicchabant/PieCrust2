import mock
from piecrust.app import PieCrust
from piecrust.appconfig import PieCrustConfiguration


def get_mock_app(config=None):
    app = mock.MagicMock(spec=PieCrust)
    app.config = PieCrustConfiguration(values={})
    return app


def get_simple_content_item(app, slug):
    src = app.getSource('pages')
    assert src is not None

    item = src.findContentFromRoute({'slug': slug})
    assert item is not None
    return item


def get_simple_page(app, slug):
    src = app.getSource('pages')
    item = get_simple_content_item(app, slug)
    return app.getPage(src, item)


from .tmpfs import (  # NOQA
    TempDirFileSystem as mock_fs,
    TempDirScope as mock_fs_scope)
