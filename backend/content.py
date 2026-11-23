import html
import re
from html.parser import HTMLParser

from fastapi import HTTPException

ALLOWED = {"p", "br", "strong", "em", "u", "s", "ul", "ol", "li"}
BLOCKED = {"script", "style", "iframe", "object", "svg", "math", "template"}


class SafeContent(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.plain = []
        self.tags = []
        self.blocked = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCKED:
            self.blocked.append(tag)
        if self.blocked:
            return
        if tag in ALLOWED:
            self.output.append(f"<{tag}>")
            if tag != "br":
                self.tags.append(tag)
            else:
                self.plain.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != "br":
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked[-1]:
                self.blocked.pop()
            return
        if tag in self.tags:
            while self.tags:
                current = self.tags.pop()
                self.output.append(f"</{current}>")
                if current in {"p", "li"}:
                    self.plain.append("\n")
                if current == tag:
                    break

    def handle_data(self, data):
        if not self.blocked:
            self.output.append(html.escape(data))
            self.plain.append(data)


def clean_content(value: str):
    parser = SafeContent()
    parser.feed(value)
    for tag in reversed(parser.tags):
        parser.output.append(f"</{tag}>")
    text = "".join(parser.plain).strip()
    if not re.sub(r"[\s\u200b\u200c\u200d\ufeff]", "", text):
        raise HTTPException(422, "写点内容再发表吧")
    if len(text) > 1000:
        raise HTTPException(422, "评论最多可写 1000 个字")
    return "".join(parser.output), text
