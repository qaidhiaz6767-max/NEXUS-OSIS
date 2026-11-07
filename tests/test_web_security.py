"""Static UI compatibility must not authorize runtime text or inline handlers."""

import base64
import hashlib
import http.client
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from app import handler_factory
from core import Store
from nexus.web_security import csp_for


def digest(body):
    return (
        "'sha256-"
        + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
        + "'"
    )


class CspTests(unittest.TestCase):
    def test_inline_blocks_use_exact_bodies_without_broad_permissions(self):
        script = "\nwindow.sample = 'NEXUS & OSIS';\n"
        style = "\nbody { color: #123456; }\n"
        policy = csp_for(
            f"<style>{style}</style><script>{script}</script>".encode(),
            "text/html; charset=utf-8",
        )
        self.assertIn("script-src 'self' " + digest(script), policy)
        self.assertIn("style-src 'self' " + digest(style), policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertNotIn("unsafe-eval", policy)
        self.assertIn("connect-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("base-uri 'none'", policy)

    def test_hashes_change_when_script_changes_and_are_deduplicated(self):
        old = csp_for(b"<script>window.sample = 1;</script>", "text/html")
        updated = csp_for(b"<script>window.sample = 2;</script>", "text/html")
        self.assertNotEqual(old, updated)
        self.assertNotIn(digest("window.sample = 1;"), updated)
        repeated = csp_for(b"<script>window.sample = 1;</script>" * 2, "text/html")
        self.assertEqual(repeated.count(digest("window.sample = 1;")), 1)

    def test_html_case_attributes_and_browser_newline_normalization(self):
        policy = csp_for(
            b'<SCRIPT data-label="a>b">\r\nwindow.sample = 1;\r</SCRIPT>', "text/html"
        )
        self.assertIn(digest("\nwindow.sample = 1;\n"), policy)

    def test_comments_external_script_bodies_and_attributes_are_not_authorized(self):
        policy = csp_for(
            b"<!-- <script>commentOnly()</script> -->"
            b'<script src="/app.js">externalFallback()</script>'
            b'<button onclick="handlerOnly()" style="color:red">Button</button>',
            "text/html",
        )
        self.assertNotIn("sha256-", policy)
        self.assertNotIn("unsafe-hashes", policy)

    def test_non_html_and_external_only_ui_keep_original_policy(self):
        baseline = csp_for(b"", "text/html")
        for media in (
            "application/json",
            "text/javascript",
            "text/css",
            "text/calendar",
        ):
            self.assertEqual(csp_for(b"<script>notHtml()</script>", media), baseline)
        self.assertEqual(
            csp_for(
                b'<link rel="stylesheet" href="/style.css"><script src="/app.js"></script>',
                "text/html",
            ),
            baseline,
        )


class StaticPolicyHttpTests(unittest.TestCase):
    def test_served_html_hashes_match_bytes_and_keep_mission_003_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            web = root / "web"
            web.mkdir()
            script = "window.syntheticUi = true;"
            html = f"<!doctype html><style>body {{color:red}}</style><script>{script}</script>".encode()
            (web / "index.html").write_bytes(html)
            store = Store(root / "osis.sqlite3")
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(store, 0))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch("app.ROOT", root):
                    for path in ("/", "/index.html"):
                        connection = http.client.HTTPConnection(
                            "127.0.0.1", server.server_port, timeout=5
                        )
                        connection.request("GET", path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.read(), html)
                        self.assertEqual(
                            response.getheader("Content-Security-Policy"),
                            csp_for(html, "text/html"),
                        )
                        self.assertIn(
                            digest(script),
                            response.getheader("Content-Security-Policy"),
                        )
                        connection.close()
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", server.server_port, timeout=5
                    )
                    connection.request("GET", "/api/capabilities")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIn(b'"persistent_plans": true', response.read())
                    connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
