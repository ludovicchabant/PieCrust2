import pytest
from mock import MagicMock
from piecrust.data.assetor import (
        Assetor, UnsupportedAssetsError, build_base_url)
from .mockutil import mock_fs, mock_fs_scope


@pytest.mark.parametrize('fs, site_root, expected', [
        (mock_fs().withPage('pages/foo/bar'), '/', {}),
        (mock_fs()
            .withPage('pages/foo/bar')
            .withPageAsset('pages/foo/bar', 'one.txt', 'one'),
            '/',
            {'one': 'one'}),
        (mock_fs()
            .withPage('pages/foo/bar')
            .withPageAsset('pages/foo/bar', 'one.txt', 'one')
            .withPageAsset('pages/foo/bar', 'two.txt', 'two'),
            '/',
            {'one': 'one', 'two': 'two'}),

        (mock_fs().withPage('pages/foo/bar'), '/whatever', {}),
        (mock_fs()
            .withPage('pages/foo/bar')
            .withPageAsset('pages/foo/bar', 'one.txt', 'one'),
            '/whatever',
            {'one': 'one'}),
        (mock_fs()
            .withPage('pages/foo/bar')
            .withPageAsset('pages/foo/bar', 'one.txt', 'one')
            .withPageAsset('pages/foo/bar', 'two.txt', 'two'),
            '/whatever',
            {'one': 'one', 'two': 'two'})
        ])
def test_assets(fs, site_root, expected):
    fs.withConfig({'site': {'root': site_root}})
    with mock_fs_scope(fs):
        page = MagicMock()
        page.app = fs.getApp(cache=False)
        page.app.env.base_asset_url_format = '%uri%'
        page.path = fs.path('/kitchen/pages/foo/bar.md')
        assetor = Assetor(page, site_root.rstrip('/') + '/foo/bar')
        for en in expected.keys():
            assert hasattr(assetor, en)
            path = site_root.rstrip('/') + '/foo/bar/%s.txt' % en
            assert getattr(assetor, en) == path
            assert assetor[en] == path


def test_missing_asset():
    with pytest.raises(KeyError):
        fs = mock_fs().withPage('pages/foo/bar')
        with mock_fs_scope(fs):
            page = MagicMock()
            page.app = fs.getApp(cache=False)
            page.path = fs.path('/kitchen/pages/foo/bar.md')
            assetor = Assetor(page, '/foo/bar')
            assetor['this_doesnt_exist']


def test_multiple_assets_with_same_name():
    with pytest.raises(UnsupportedAssetsError):
        fs = (mock_fs()
                .withPage('pages/foo/bar')
                .withPageAsset('pages/foo/bar', 'one.txt', 'one text')
                .withPageAsset('pages/foo/bar', 'one.jpg', 'one picture'))
        with mock_fs_scope(fs):
            page = MagicMock()
            page.app = fs.getApp(cache=False)
            page.path = fs.path('/kitchen/pages/foo/bar.md')
            assetor = Assetor(page, '/foo/bar')
            assetor['one']


@pytest.mark.parametrize('url_format, pretty_urls, uri, expected', [
        ('%uri%', True, '/foo', '/foo/'),
        ('%uri%', True, '/foo.ext', '/foo.ext/'),
        ('%uri%', False, '/foo.html', '/foo/'),
        ('%uri%', False, '/foo.ext', '/foo/'),
        ])
def test_build_base_url(url_format, pretty_urls, uri, expected):
    app = MagicMock()
    app.env = MagicMock()
    app.env.base_asset_url_format = url_format
    app.config = {
            'site/root': '/',
            'site/pretty_urls': pretty_urls}
    assets_path = 'foo/bar-assets'
    actual = build_base_url(app, uri, assets_path)
    assert actual == expected

