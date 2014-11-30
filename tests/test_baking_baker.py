import os.path
import pytest
from piecrust.baking.baker import PageBaker, Baker
from piecrust.baking.records import BakeRecord
from .mockutil import get_mock_app, mock_fs, mock_fs_scope


@pytest.mark.parametrize('uri, page_num, pretty, expected', [
        # Pretty URLs
        ('', 1, True, 'index.html'),
        ('', 2, True, '2/index.html'),
        ('foo', 1, True, 'foo/index.html'),
        ('foo', 2, True, 'foo/2/index.html'),
        ('foo/bar', 1, True, 'foo/bar/index.html'),
        ('foo/bar', 2, True, 'foo/bar/2/index.html'),
        ('foo.ext', 1, True, 'foo.ext/index.html'),
        ('foo.ext', 2, True, 'foo.ext/2/index.html'),
        ('foo/bar.ext', 1, True, 'foo/bar.ext/index.html'),
        ('foo/bar.ext', 2, True, 'foo/bar.ext/2/index.html'),
        ('foo.bar.ext', 1, True, 'foo.bar.ext/index.html'),
        ('foo.bar.ext', 2, True, 'foo.bar.ext/2/index.html'),
        # Ugly URLs
        ('', 1, False, 'index.html'),
        ('', 2, False, '2.html'),
        ('foo', 1, False, 'foo.html'),
        ('foo', 2, False, 'foo/2.html'),
        ('foo/bar', 1, False, 'foo/bar.html'),
        ('foo/bar', 2, False, 'foo/bar/2.html'),
        ('foo.ext', 1, False, 'foo.ext'),
        ('foo.ext', 2, False, 'foo/2.ext'),
        ('foo/bar.ext', 1, False, 'foo/bar.ext'),
        ('foo/bar.ext', 2, False, 'foo/bar/2.ext'),
        ('foo.bar.ext', 1, False, 'foo.bar.ext'),
        ('foo.bar.ext', 2, False, 'foo.bar/2.ext')
        ])
def test_get_output_path(uri, page_num, pretty, expected):
    app = get_mock_app()
    if pretty:
        app.config.set('site/pretty_urls', True)
    assert app.config.get('site/pretty_urls') == pretty

    baker = PageBaker(app, '/destination')
    sub_uri = baker.getOutputUri(uri, page_num)
    path = baker.getOutputPath(sub_uri)
    expected = os.path.normpath(
            os.path.join('/destination', expected))
    assert expected == path


def test_empty_bake():
    fs = mock_fs()
    with mock_fs_scope(fs):
        out_dir = fs.path('kitchen/_counter')
        assert not os.path.isdir(out_dir)
        app = fs.getApp()
        baker = Baker(app, out_dir)
        baker.bake()
        assert os.path.isdir(out_dir)
        structure = fs.getStructure('kitchen/_counter')
        assert list(structure.keys()) == ['index.html']


def test_simple_bake():
    fs = (mock_fs()
            .withPage('posts/2010-01-01_post1.md', {'layout': 'none', 'format': 'none'}, 'post one')
            .withPage('pages/_index.md', {'layout': 'none', 'format': 'none'}, "something"))
    with mock_fs_scope(fs):
        out_dir = fs.path('kitchen/_counter')
        app = fs.getApp()
        baker = Baker(app, out_dir)
        baker.bake()
        structure = fs.getStructure('kitchen/_counter')
        assert structure == {
                '2010': {'01': {'01': {'post1.html': 'post one'}}},
                'index.html': 'something'}

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

