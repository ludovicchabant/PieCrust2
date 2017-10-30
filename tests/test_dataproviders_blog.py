from .mockutil import mock_fs, mock_fs_scope
from .rdrutil import render_simple_page


def _get_post_tokens(i, posts_per_month=2, posts_per_year=5, first_year=2001):
    year = first_year + int(i / posts_per_year)
    i_in_year = i % posts_per_year
    month = int(i_in_year / posts_per_month) + 1
    day = i_in_year % posts_per_month + 1
    return (year, month, day, i + 1)


def test_blog_provider_archives():
    fs = (mock_fs()
          .withConfig({
              'site': {
                  'default_layout': 'none',
                  'default_format': 'none'
              }
          })
          .withPages(
              20,
              lambda i: ('posts/%04d-%02d-%02d_post-%d.md' %
                         _get_post_tokens(i)),
              lambda i: {'title': "Post %02d" % (i + 1), 'format': 'none'},
              lambda i: "This is post %02d" % (i + 1))
          .withPage('pages/allposts.html',
                    {'layout': 'none'},
                    "{%for p in blog.posts-%}\n"
                    "{{p.title}}\n"
                    "{%endfor%}\n")
          .withPage('pages/allyears.html',
                    {'layout': 'none'},
                    "{%for y in blog.years-%}\n"
                    "YEAR={{y}}\n"
                    "{%for p in y.posts-%}\n"
                    "{{p.title}}\n"
                    "{%endfor%}\n"
                    "{%endfor%}")
          .withFile('kitchen/templates/_year.html',
                    "YEAR={{year}}\n"
                    "{%for p in archives-%}\n"
                    "{{p.title}}\n"
                    "{%endfor%}\n"
                    "\n"
                    "{%for m in monthly_archives-%}\n"
                    "MONTH={{m.timestamp|date('%m')}}\n"
                    "{%for p in m.posts-%}\n"
                    "{{p.title}}\n"
                    "{%endfor%}\n"
                    "{%endfor%}"))

    with mock_fs_scope(fs):
        fs.runChef('bake', '-o', fs.path('counter'))

        # Check `allposts`.
        # Should have all the posts. Duh.
        expected = '\n'.join(map(lambda i: "Post %02d" % i,
                                 range(20, 0, -1))) + '\n'
        actual = fs.getFileEntry('counter/allposts.html')
        assert expected == actual

        # Check `allyears`.
        # Should have all the years, each with 5 posts in reverse
        # chronological order.
        expected = ''
        cur_index = 20
        for y in range(2004, 2000, -1):
            expected += ('YEAR=%04d\n' % y) + '\n'.join(
                map(lambda i: "Post %02d" % i,
                    range(cur_index, cur_index - 5, -1))) + '\n\n'
            cur_index -= 5
        actual = fs.getFileEntry('counter/allyears.html')
        assert expected == actual

        # Check each yearly page.
        # Should have both the posts for that year (5 posts) in
        # chronological order, followed by the months for that year
        # (3 months) and the posts in each month (2, 2, and 1).
        cur_index = 1
        for y in range(2001, 2005):
            orig_index = cur_index
            expected = ('YEAR=%04d\n' % y) + '\n'.join(
                map(lambda i: "Post %02d" % i,
                    range(cur_index, cur_index + 5))) + '\n'
            expected += "\n\n"
            orig_final_index = cur_index
            cur_index = orig_index
            for m in range(1, 4):
                expected += 'MONTH=%02d\n' % m
                expected += '\n'.join(
                    map(lambda i: "Post %02d" % i,
                        range(cur_index,
                              min(cur_index + 2, orig_index + 5)))) + '\n'
                expected += '\n'
                cur_index += 2
            cur_index = orig_final_index

            actual = fs.getFileEntry('counter/archives/%04d.html' % y)
            assert expected == actual
            cur_index += 5


def test_blog_provider_tags():
    fs = (mock_fs()
          .withConfig()
          .withPage('posts/2015-03-01_one.md',
                    {'title': 'One', 'tags': ['Foo']})
          .withPage('posts/2015-03-02_two.md',
                    {'title': 'Two', 'tags': ['Foo']})
          .withPage('posts/2015-03-03_three.md',
                    {'title': 'Three', 'tags': ['Bar']})
          .withPage('pages/tags.md',
                    {'format': 'none', 'layout': 'none'},
                    "{%for c in blog.tags%}\n"
                    "{{c.name}} ({{c.post_count}})\n"
                    "{%endfor%}\n"))
    with mock_fs_scope(fs):
        page = fs.getSimplePage('tags.md')
        actual = render_simple_page(page)
        expected = "\nBar (1)\n\nFoo (2)\n"
        assert actual == expected

