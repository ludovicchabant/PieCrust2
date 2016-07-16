from html.parser import HTMLParser


def text_preview(txt, length=100, *, max_length=None, offset=0):
    max_length = max_length or (length + 50)
    extract = txt[offset:offset + length]
    if len(txt) > offset + length:
        for i in range(offset + length,
                       min(offset + max_length, len(txt))):
            c = txt[i]
            if c not in [' ', '\t', '\r', '\n']:
                extract += c
            else:
                extract += '...'
                break
    return extract


class MLStripper(HTMLParser):
    def __init__(self):
        super(MLStripper, self).__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def handle_entityref(self, name):
        self.fed.append('&%s;' % name)

    def get_data(self):
        return ''.join(self.fed)


def html_to_text(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

