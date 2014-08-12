import pytest
from piecrust.page import parse_segments



test_parse_segments_data1 = ("", {'content': ''})
test_parse_segments_data2 = ("Foo bar", {'content': 'Foo bar'})
test_parse_segments_data3 = ("""Something that spans
several lines
like this""",
        {'content': """Something that spans
several lines
like this"""})
test_parse_segments_data4 = ("""Blah blah
---foo---
Something else
---bar---
Last thing
""",
        {
            'content': "Blah blah\n",
            'foo': "Something else\n",
            'bar': "Last thing\n"})
test_parse_segments_data5 = ("""Blah blah
<--textile-->
Here's some textile
""",
        {
            'content': [
                ("Blah blah\n", None),
                ("Here's some textile\n", 'textile')]})
test_parse_segments_data6 = ("""Blah blah
Whatever
<--textile-->
Oh well, that's good
---foo---
Another segment
With another...
<--change-->
...of formatting.
""",
        {
            'content': [
                ("Blah blah\nWhatever\n", None),
                ("Oh well, that's good\n", 'textile')],
            'foo': [
                ("Another segment\nWith another...\n", None),
                ("...of formatting.\n", 'change')]})

@pytest.mark.parametrize('text, expected', [
        test_parse_segments_data1,
        test_parse_segments_data2,
        test_parse_segments_data3,
        test_parse_segments_data4,
        test_parse_segments_data5,
        test_parse_segments_data6,
    ])
def test_parse_segments(text, expected):
    actual = parse_segments(text)
    assert actual is not None
    assert list(actual.keys()) == list(expected.keys())
    for key, val in expected.items():
        if isinstance(val, str):
            assert len(actual[key].parts) == 1
            assert actual[key].parts[0].content == val
            assert actual[key].parts[0].fmt is None
        else:
            assert len(actual[key].parts) == len(val)
            for i, part in enumerate(val):
                assert actual[key].parts[i].content == part[0]
                assert actual[key].parts[i].fmt == part[1]

