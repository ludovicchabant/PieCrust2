import time
import os.path
import pytest
from piecrust.baking.baker import PageBaker, Baker
from piecrust.baking.records import BakeRecord
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

    for site_root in ['/', '/whatever/']:
        app.config.set('site/root', site_root)
        baker = PageBaker(app, '/destination')
        path = baker.getOutputPath(site_root + uri)
        expected = os.path.normpath(
                os.path.join('/destination', expected))
        assert expected == path


def test_removed():
    fs = (mock_fs()
            .withPage('pages/foo.md', {'layout': 'none', 'format': 'none'}, 'a foo page')
            .withPage('pages/_index.md', {'layout': 'none', 'format': 'none'}, "something"))
    with mock_fs_scope(fs):
        out_dir = fs.path('kitchen/_counter')
        app = fs.getApp()
        baker = Baker(app, out_dir)
        baker.bake()
        structure = fs.getStructure('kitchen/_counter')
        assert structure == {
                'foo.html': 'a foo page',
                'index.html': 'something'}

        os.remove(fs.path('kitchen/pages/foo.md'))
        app = fs.getApp()
        baker = Baker(app, out_dir)
        baker.bake()
        structure = fs.getStructure('kitchen/_counter')
        assert structure == {
                'index.html': 'something'}


def test_record_version_change():
    fs = (mock_fs()
            .withPage('pages/foo.md', {'layout': 'none', 'format': 'none'}, 'a foo page'))
    with mock_fs_scope(fs):
        out_dir = fs.path('kitchen/_counter')
        app = fs.getApp()
        baker = Baker(app, out_dir)
        baker.bake()
        mtime = os.path.getmtime(fs.path('kitchen/_counter/foo.html'))
        time.sleep(1)

        app = fs.getApp()
        baker = Baker(app, out_dir)
        baker.bake()
        assert mtime == os.path.getmtime(fs.path('kitchen/_counter/foo.html'))

        BakeRecord.RECORD_VERSION += 1
        try:
            app = fs.getApp()
            baker = Baker(app, out_dir)
            baker.bake()
            assert mtime < os.path.getmtime(fs.path('kitchen/_counter/foo.html'))
        finally:
            BakeRecord.RECORD_VERSION -= 1

