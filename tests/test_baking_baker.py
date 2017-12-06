import time
from .mockutil import get_mock_app, mock_fs, mock_fs_scope


def test_bake_and_add_post():
    fs = (mock_fs()
          .withConfig()
          .withPage('pages/_index.html', {'layout': 'none', 'format': 'none'},
                    "{% for p in pagination.posts -%}\n"
                    "{{p.title}}\n"
                    "{% endfor %}")
          .withPage('posts/2017-01-01_first.html', {'title': "First"},
                    "something"))
    with mock_fs_scope(fs):
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'First\n'

        time.sleep(1)
        fs.withPage('posts/2017-01-02_second.html', {'title': "Second"},
                    "something else")
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second\nFirst\n'


def test_bake_four_times():
    fs = (mock_fs()
          .withConfig({'site': {
              'default_format': 'none',
              'default_page_layout': 'none',
              'default_post_layout': 'none',
          }})
          .withPage('pages/_index.html', {'layout': 'none', 'format': 'none'},
                    "{% for p in pagination.posts -%}\n"
                    "{{p.title}}\n"
                    "{% endfor %}")
          .withPage('posts/2017-01-01_first.html', {'title': "First"},
                    "something 1")
          .withPage('posts/2017-01-02_second.html', {'title': "Second"},
                    "something 2"))
    with mock_fs_scope(fs):
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second\nFirst\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'

        print("\n\n\n")
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second\nFirst\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'

        print("\n\n\n")
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second\nFirst\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'

        print("\n\n\n")
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second\nFirst\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'


def test_bake_four_times_again():
    fs = (mock_fs()
          .withConfig({'site': {
              'default_format': 'none',
              'default_page_layout': 'none',
              'default_post_layout': 'none',
          }})
          .withPage('pages/_index.html', {'layout': 'none', 'format': 'none'},
                    "{% for p in pagination.posts -%}\n"
                    "{{p.title}} : {{p.content}}\n"
                    "{% endfor %}")
          .withPage('posts/2017-01-01_first.html', {'title': "First"},
                    "something 1")
          .withPage('posts/2017-01-02_second.html', {'title': "Second"},
                    "something 2"))
    with mock_fs_scope(fs):
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second : something 2\nFirst : something 1\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'

        print("\n\n\n")
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second : something 2\nFirst : something 1\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'

        print("\n\n\n")
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second : something 2\nFirst : something 1\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'

        print("\n\n\n")
        fs.runChef('bake')
        structure = fs.getStructure('kitchen/_counter')
        assert structure['index.html'] == 'Second : something 2\nFirst : something 1\n'
        assert structure['2017']['01']['01']['first.html'] == 'something 1'
        assert structure['2017']['01']['02']['second.html'] == 'something 2'

