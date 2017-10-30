import time
import os.path
import urllib.parse
import pytest
from piecrust.pipelines.records import MultiRecord
from piecrust.pipelines._pagebaker import get_output_path
from .mockutil import get_mock_app, mock_fs, mock_fs_scope


@pytest.mark.parametrize('uri, pretty, expected', [
    # Pretty URLs
    ('', True, 'index.html'),
    ('2', True, '2/index.html'),
    ('foo', True, 'foo/index.html'),
    ('foo/2', True, 'foo/2/index.html'),
    ('foo/bar', True, 'foo/bar/index.html'),
    ('foo/bar/2', True, 'foo/bar/2/index.html'),
    ('foo.ext', True, 'foo.ext/index.html'),
    ('foo.ext/2', True, 'foo.ext/2/index.html'),
    ('foo/bar.ext', True, 'foo/bar.ext/index.html'),
    ('foo/bar.ext/2', True, 'foo/bar.ext/2/index.html'),
    ('foo.bar.ext', True, 'foo.bar.ext/index.html'),
    ('foo.bar.ext/2', True, 'foo.bar.ext/2/index.html'),
    # Ugly URLs
    ('', False, 'index.html'),
    ('2.html', False, '2.html'),
    ('foo.html', False, 'foo.html'),
    ('foo/2.html', False, 'foo/2.html'),
    ('foo/bar.html', False, 'foo/bar.html'),
    ('foo/bar/2.html', False, 'foo/bar/2.html'),
    ('foo.ext', False, 'foo.ext'),
    ('foo/2.ext', False, 'foo/2.ext'),
    ('foo/bar.ext', False, 'foo/bar.ext'),
    ('foo/bar/2.ext', False, 'foo/bar/2.ext'),
    ('foo.bar.ext', False, 'foo.bar.ext'),
    ('foo.bar/2.ext', False, 'foo.bar/2.ext')
])
def test_get_output_path(uri, pretty, expected):
    app = get_mock_app()
    if pretty:
        app.config.set('site/pretty_urls', True)
    assert app.config.get('site/pretty_urls') == pretty

    out_dir = '/destination'

    for site_root in ['/', '/whatever/', '/~johndoe/']:
        app.config.set('site/root', urllib.parse.quote(site_root))
        path = get_output_path(app, out_dir,
                               urllib.parse.quote(site_root) + uri,
                               pretty)
        expected = os.path.normpath(
            os.path.join('/destination', expected))
        assert expected == path


def test_removed():
    fs = (mock_fs()
          .withConfig()
          .withPage('pages/foo.md', {'layout': 'none', 'format': 'none'},
                    "a foo page")
          .withPage('pages/_index.md', {'layout': 'none', 'format': 'none'},
                    "something"))
    with mock_fs_scope(fs):
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure == {
            'foo.html': 'a foo page',
            'index.html': 'something'}

        os.remove(fs.path('kitchen/pages/foo.md'))
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure == {
            'index.html': 'something'}


def test_record_version_change():
    fs = (mock_fs()
          .withConfig()
          .withPage('pages/foo.md', {'layout': 'none', 'format': 'none'},
                    'a foo page'))
    with mock_fs_scope(fs):
        time.sleep(1)
        fs.runChef('bake', '-o', fs.path('counter'))
        time.sleep(0.1)
        mtime = os.path.getmtime(fs.path('counter/foo.html'))

        time.sleep(1)
        fs.runChef('bake', '-o', fs.path('counter'))
        time.sleep(0.1)
        assert mtime == os.path.getmtime(fs.path('counter/foo.html'))

        MultiRecord.RECORD_VERSION += 1
        try:
            time.sleep(1)
            fs.runChef('bake', '-o', fs.path('counter'))
            time.sleep(0.1)
            assert mtime < os.path.getmtime(fs.path('counter/foo.html'))
        finally:
            MultiRecord.RECORD_VERSION -= 1

