import pytest
from piecrust.data.assetor import Assetor, UnsupportedAssetsError
from .mockutil import mock_fs, mock_fs_scope, get_simple_page


@pytest.mark.parametrize('fs_fac, site_root, expected', [
    (lambda: mock_fs().withPage('pages/foo/bar'), '/', {}),
    (lambda: mock_fs()
     .withPage('pages/foo/bar')
     .withPageAsset('pages/foo/bar', 'one.txt', 'one'),
     '/',
     {'one': 'one'}),
    (lambda: mock_fs()
     .withPage('pages/foo/bar')
     .withPageAsset('pages/foo/bar', 'one.txt', 'one')
     .withPageAsset('pages/foo/bar', 'two.txt', 'two'),
     '/',
     {'one': 'one', 'two': 'two'}),

    (lambda: mock_fs().withPage('pages/foo/bar'), '/whatever', {}),
    (lambda: mock_fs()
     .withPage('pages/foo/bar')
     .withPageAsset('pages/foo/bar', 'one.txt', 'one'),
     '/whatever',
     {'one': 'one'}),
    (lambda: mock_fs()
     .withPage('pages/foo/bar')
     .withPageAsset('pages/foo/bar', 'one.txt', 'one')
     .withPageAsset('pages/foo/bar', 'two.txt', 'two'),
     '/whatever',
     {'one': 'one', 'two': 'two'})
])
def test_assets(fs_fac, site_root, expected):
    fs = fs_fac()
    fs.withConfig({'site': {'root': site_root}})
    with mock_fs_scope(fs):
        app = fs.getApp()
        app.config.set('site/asset_url_format', '%page_uri%/%filename%')
        page = get_simple_page(app, 'foo/bar')

        assetor = Assetor(page)
        for en in expected.keys():
            assert en in assetor
            assert hasattr(assetor, en)
            path = site_root.rstrip('/') + '/foo/bar/%s.txt' % en
            assert str(assetor[en]) == path
            assert str(getattr(assetor, en)) == path


def test_missing_asset():
    with pytest.raises(KeyError):
        fs = (mock_fs()
              .withConfig()
              .withPage('pages/foo/bar'))
        with mock_fs_scope(fs):
            app = fs.getApp()
            app.config.set('site/asset_url_format', '%page_uri%/%filename%')
            page = get_simple_page(app, 'foo/bar')

            assetor = Assetor(page)
            assetor['this_doesnt_exist']


def test_multiple_assets_with_same_name():
    with pytest.raises(UnsupportedAssetsError):
        fs = (mock_fs()
              .withConfig()
              .withPage('pages/foo/bar')
              .withPageAsset('pages/foo/bar', 'one.txt', 'one text')
              .withPageAsset('pages/foo/bar', 'one.jpg', 'one picture'))
        with mock_fs_scope(fs):
            app = fs.getApp()
            app.config.set('site/asset_url_format', '%page_uri%/%filename%')
            page = get_simple_page(app, 'foo/bar')

            assetor = Assetor(page)
            assetor['one']
