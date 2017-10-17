import math
import pytest
from piecrust.data.paginator import Paginator


class MockSource(list):
    def __init__(self, count):
        for i in range(count):
            self.append('item %d' % i)


@pytest.mark.parametrize('uri, page_num, count', [
    ('', 1, 0),
    ('', 1, 4),
    ('', 1, 5),
    ('', 1, 8),
    ('', 1, 14),
    ('', 2, 8),
    ('', 2, 14),
    ('', 3, 14),
    ('blog', 1, 0),
    ('blog', 1, 4),
    ('blog', 1, 5),
    ('blog', 1, 8),
    ('blog', 1, 14),
    ('blog', 2, 8),
    ('blog', 2, 14),
    ('blog', 3, 14)
])
def test_paginator(uri, page_num, count):
    def _get_mock_uri(sub_num):
        res = uri
        if sub_num > 1:
            if res != '' and not res.endswith('/'):
                res += '/'
            res += '%d' % sub_num
        return res

    source = MockSource(count)
    p = Paginator(source, None, page_num)
    p._items_per_page = 5
    p._getPageUri = _get_mock_uri

    if count <= 5:
        # All posts fit on the page
        assert p.prev_page_number is None
        assert p.prev_page is None
        assert p.this_page_number == 1
        assert p.this_page == uri
        assert p.next_page_number is None
        assert p.next_page is None
    elif page_num == 1:
        # First page in many
        assert p.prev_page_number is None
        assert p.prev_page is None
        assert p.this_page_number == 1
        assert p.this_page == uri
        assert p.next_page_number == 2
        np = '2' if uri == '' else (uri + '/2')
        assert p.next_page == np
    else:
        # Page in the middle of it all
        assert p.prev_page_number == page_num - 1
        if page_num == 2:
            assert p.prev_page == uri
        else:
            pp = str(page_num - 1) if uri == '' else (
                '%s/%d' % (uri, page_num - 1))
            assert p.prev_page == pp

        assert p.this_page_number == page_num
        tp = str(page_num) if uri == '' else (
            '%s/%d' % (uri, page_num))
        assert p.this_page == tp

        if page_num * 5 > count:
            assert p.next_page_number is None
            assert p.next_page is None
        else:
            assert p.next_page_number == page_num + 1
            np = str(page_num + 1) if uri == '' else (
                '%s/%d' % (uri, page_num + 1))
            assert p.next_page == np

    assert p.total_post_count == count
    page_count = math.ceil(count / 5.0)
    assert p.total_page_count == page_count
    assert p.all_page_numbers() == list(range(1, page_count + 1))

    for radius in range(1, 8):
        width = radius * 2 + 1
        if page_count == 0:
            nums = []
        else:
            nums = list(filter(
                lambda i: i >= 1 and i <= page_count,
                range(page_num - radius, page_num + radius + 1)))
            if len(nums) < width:
                to_add = width - len(nums)
                if nums[0] > 1:
                    to_add = min(to_add, nums[0] - 1)
                    nums = list(range(1, to_add + 1)) + nums
                else:
                    to_add = min(to_add, page_count - nums[-1])
                    nums = nums + list(range(nums[-1] + 1,
                                             nums[-1] + to_add + 1))
        assert nums == p.all_page_numbers(radius)

    itp = count
    if count > 5:
        if page_num * 5 < count:
            itp = 5
        else:
            itp = count % 5
    assert p.items_this_page == itp

    indices = list(range(count))
    indices = indices[(page_num - 1) * 5:(page_num - 1) * 5 + itp]
    expected = list(['item %d' % i for i in indices])
    items = list(p.items)
    assert items == expected

