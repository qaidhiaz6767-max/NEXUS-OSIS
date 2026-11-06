"""HTTP-level regression checks; all requests stay on loopback."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import handler_factory
from core import Store


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.sqlite3")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(self.store, 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def request(self, method, path, headers=None, body=None):
        port = self.server.server_port
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        req_headers = {"Host": f"127.0.0.1:{port}"}
        req_headers.update(headers or {})
        connection.request(method, path, body=body, headers=req_headers)
        response = connection.getresponse()
        status = response.status
        payload = response.read()
        connection.close()
        return status, payload

    def test_valid_host_state(self):
        status, body = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertIn("tasks", json.loads(body))

    def test_unknown_host_blocked(self):
        status, _ = self.request("GET", "/api/state", {"Host": "attack.example"})
        self.assertEqual(status, 403)

    def test_post_requires_local_header(self):
        status, _ = self.request("POST", "/api/chat", {"Content-Type": "application/json"}, b'{"message":"/brief"}')
        self.assertEqual(status, 403)

    def test_post_rejects_cross_origin(self):
        status, _ = self.request("POST", "/api/chat", {"Content-Type": "application/json", "X-NEXUS-Local": "1", "Origin": "https://attack.example"}, b'{"message":"/brief"}')
        self.assertEqual(status, 403)

    def test_oversize_post_rejected(self):
        headers = {"Content-Type": "application/json", "X-NEXUS-Local": "1"}
        status, _ = self.request("POST", "/api/chat", headers, b"x" * 16001)
        self.assertEqual(status, 400)

    def test_proposal_approval_over_http(self):
        headers = {"Content-Type": "application/json", "X-NEXUS-Local": "1"}
        cmd = json.dumps({"message": "/task add Draft agenda | OSIS secretary | 2026-11-20 | high"}).encode()
        status, raw = self.request("POST", "/api/chat", headers, cmd)
        self.assertEqual(status, 200)
        response = json.loads(raw)
        self.assertEqual(self.store.state()["tasks"], [])
        approval = json.dumps({"id": response["pending"]["id"], "approve": True}).encode()
        status, raw = self.request("POST", "/api/decide", headers, approval)
        self.assertEqual(status, 200)
        self.assertEqual(len(self.store.state()["tasks"]), 1)
        status, _ = self.request("POST", "/api/decide", headers, approval)
        self.assertEqual(status, 400)

    def test_dashboard_v02_served_without_external_assets(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        markup = body.decode("utf-8")
        self.assertIn('id="view-overview"', markup)
        self.assertIn('id="view-assistant"', markup)
        self.assertIn('id="view-approvals"', markup)
        self.assertNotIn('https://cdn.', markup)

    def test_dashboard_assets_served(self):
        for path, snippet in (("/style.css", "--page:"), ("/app.js", "Approval")):
            status, body = self.request("GET", path)
            self.assertEqual(status, 200)
            self.assertIn(snippet, body.decode("utf-8"))

    def test_valid_offline_brief(self):
        status, body = self.request("POST", "/api/chat", {"Content-Type": "application/json", "X-NEXUS-Local": "1"}, b'{"message":"/brief"}')
        self.assertEqual(status, 200)
        self.assertIn("OSIS BRIEFING", json.loads(body)["message"])


if __name__ == "__main__":
    unittest.main()
