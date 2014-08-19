import os.path
import pytest
from piecrust.baking.baker import PageBaker
from .mockutil import get_mock_app


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

