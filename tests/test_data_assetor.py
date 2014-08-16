import pytest
from mock import MagicMock
from piecrust.data.assetor import Assetor, UnsupportedAssetsError
from .mockutil import mock_fs, mock_fs_scope


@pytest.mark.parametrize('fs, expected', [
        (mock_fs().withPage('foo/bar'), {}),
        (mock_fs()
            .withPage('foo/bar')
            .withPageAsset('foo/bar', 'one.txt', 'one'),
            {'one': 'one'}),
        (mock_fs()
            .withPage('foo/bar')
            .withPageAsset('foo/bar', 'one.txt', 'one')
            .withPageAsset('foo/bar', 'two.txt', 'two'),
            {'one': 'one', 'two': 'two'})
        ])
def test_assets(fs, expected):
    with mock_fs_scope(fs):
        page = MagicMock()
        page.app = fs.getApp()
        page.path = fs.path('/kitchen/_content/pages/foo/bar.md')
        assetor = Assetor(page, '/foo/bar')
        for en in expected.keys():
            assert hasattr(assetor, en)
            path = '/foo/bar/%s.txt' % en
            assert getattr(assetor, en) == path
            assert assetor[en] == path


def test_missing_asset():
    with pytest.raises(KeyError):
        fs = mock_fs().withPage('foo/bar')
        with mock_fs_scope(fs):
            page = MagicMock()
            page.app = fs.getApp()
            page.path = fs.path('/kitchen/_content/pages/foo/bar.md')
            assetor = Assetor(page, '/foo/bar')
            assetor['this_doesnt_exist']


def test_multiple_assets_with_same_name():
    with pytest.raises(UnsupportedAssetsError):
        fs = (mock_fs()
                .withPage('foo/bar')
                .withPageAsset('foo/bar', 'one.txt', 'one text')
                .withPageAsset('foo/bar', 'one.jpg', 'one picture'))
        with mock_fs_scope(fs):
            page = MagicMock()
            page.app = fs.getApp()
            page.path = fs.path('/kitchen/_content/pages/foo/bar.md')
            assetor = Assetor(page, '/foo/bar')
            assetor['one']

