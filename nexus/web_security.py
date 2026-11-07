"""Content Security Policy for trusted static HTML, including single-file UIs.

Never use this to authorize HTML assembled from model output or user records.
Hashes authorize static script/style bodies, not handlers or style attributes.
"""

import base64
import hashlib
from html.parser import HTMLParser


class _InlineBlocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.hashes = {"style": set(), "script": set()}
        self.active = None
        self.parts = []
        self.external = False

    def handle_starttag(self, tag, attrs):
        if tag in self.hashes and self.active is None:
            self.active = tag
            self.parts = []
            self.external = tag == "script" and any(key == "src" for key, _ in attrs)

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag != self.active:
            return
        body = "".join(self.parts)
        if body.strip() and not self.external:
            digest = base64.b64encode(
                hashlib.sha256(body.encode("utf-8")).digest()
            ).decode()
            self.hashes[tag].add(f"'sha256-{digest}'")
        self.active = None
        self.parts = []


def csp_for(data: bytes, content_type: str) -> str:
    """Authorize only inline blocks in the trusted HTML response being served."""
    sources = {"style": ["'self'"], "script": ["'self'"]}
    if content_type.partition(";")[0].strip().lower() == "text/html":
        parser = _InlineBlocks()
        # HTML normalizes newlines before calculating inline CSP hashes.
        markup = (
            data.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
        )
        parser.feed(markup)
        parser.close()
        for tag in sources:
            sources[tag].extend(sorted(parser.hashes[tag]))
    return (
        f"default-src 'self'; style-src {' '.join(sources['style'])}; "
        f"script-src {' '.join(sources['script'])}; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
        "frame-ancestors 'none'; base-uri 'none'"
    )
