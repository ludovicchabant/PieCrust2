import pytest
from piecrust.page import parse_segments, _count_lines


test_parse_segments_data1 = ("", {'content': ''})
test_parse_segments_data2 = ("Foo bar", {'content': 'Foo bar'})
test_parse_segments_data3 = (
    """Something that spans
several lines
like this""",
    {'content': """Something that spans
several lines
like this"""})
test_parse_segments_data4 = (
    """Blah blah
---foo---
Something else
---bar---
Last thing
""",
    {
        'content': "Blah blah\n",
        'foo': "Something else\n",
        'bar': "Last thing\n"})


@pytest.mark.parametrize('text, expected', [
    test_parse_segments_data1,
    test_parse_segments_data2,
    test_parse_segments_data3,
    test_parse_segments_data4,
])
def test_parse_segments(text, expected):
    actual = parse_segments(text)
    assert actual is not None
    assert list(actual.keys()) == list(expected.keys())
    for key, val in expected.items():
        assert actual[key].content == val
        assert actual[key].fmt is None


@pytest.mark.parametrize('text, expected', [
    ('', 1),
    ('\n', 2),
    ('blah foo', 1),
    ('blah foo\n', 2),
    ('blah foo\nmore here', 2),
    ('blah foo\nmore here\n', 3),
    ('\nblah foo\nmore here\n', 4),
])
def test_count_lines(text, expected):
    actual = _count_lines(text)
    assert actual == expected


@pytest.mark.parametrize('text, start, end, expected', [
    ('', 0, -1, 1),
    ('\n', 1, -1, 1),
    ('blah foo', 2, 4, 1),
    ('blah foo\n', 2, 4, 1),
    ('blah foo\nmore here', 4, -1, 2),
    ('blah foo\nmore here\n', 10, -1, 2),
    ('\nblah foo\nmore here\n', 2, -1, 3),
])
def test_count_lines_with_offsets(text, start, end, expected):
    actual = _count_lines(text, start, end)
    assert actual == expected
