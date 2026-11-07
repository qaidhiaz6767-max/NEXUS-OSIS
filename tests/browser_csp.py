"""Optional real-browser CSP test with trusted, synthetic single-file HTML."""

import json
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from app import handler_factory
from core import Store


MARKUP = """<!doctype html><html><head><meta charset="utf-8">
<style>body { --nexus-inline-style: approved; }</style>
</head><body><p id="status">Loading</p>
<button id="blocked-handler" onclick="window.handlerRan = true">Test handler</button>
<script>
window.violations = [];
document.addEventListener('securitypolicyviolation', event => {
  window.violations.push(event.effectiveDirective);
});
document.addEventListener('DOMContentLoaded', async () => {
  const response = await fetch('/api/capabilities?workspace=osis');
  const capabilities = await response.json();
  document.getElementById('status').textContent =
    capabilities.features.persistent_plans ? 'Mission 003 connected' : 'Failed';
});
</script></body></html>"""


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "web").mkdir()
    (root / "web" / "index.html").write_bytes(MARKUP.encode())
    store = Store(root / "osis.sqlite3")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_factory(store, 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("app.ROOT", root), sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=__import__("os").environ.get("NEXUS_CHROMIUM","/usr/bin/chromium"),
                headless=True,
                args=["--no-sandbox"],
            )
            page = browser.new_page()
            external = []
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "request",
                lambda request: (
                    external.append(request.url)
                    if not request.url.startswith(
                        f"http://127.0.0.1:{server.server_port}/"
                    )
                    else None
                ),
            )
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.wait_for_function(
                "document.getElementById('status').textContent === 'Mission 003 connected'"
            )
            assert (
                page.evaluate(
                    "getComputedStyle(document.body).getPropertyValue('--nexus-inline-style').trim()"
                )
                == "approved"
            )
            page.locator("#blocked-handler").click()
            page.evaluate(
                """() => {
              const injected = document.createElement('script');
              injected.textContent = 'window.injectedRan = true;';
              document.body.appendChild(injected);
            }"""
            )
            page.wait_for_function(
                "window.violations.includes('script-src-attr') && window.violations.includes('script-src-elem')"
            )
            assert not page.evaluate("Boolean(window.handlerRan || window.injectedRan)")
            assert not external, external
            assert not errors, errors
            assert store.state()["tasks"] == []
            browser.close()
            print(
                json.dumps(
                    {
                        "browser": "Chromium on Linux",
                        "inline_script_and_style": "passed",
                        "mission_003_api": "passed",
                        "unlisted_script_and_event_handler": "blocked",
                        "external_requests": len(external),
                    }
                )
            )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
