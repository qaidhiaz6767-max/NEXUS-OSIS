"""Local-only HTTP and CLI entry point for NEXUS OSIS.
Start: python3 app.py
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import threading
import tempfile
import time
import webbrowser
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, HTTPRedirectHandler, build_opener

from core import Coordinator, Store, HELP
from nexus.validation import configured_timezone
from nexus.backend_api import get_data
from nexus.workspaces import WorkspaceRegistry
from nexus.web_security import csp_for

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = Path(os.environ.get("NEXUS_DB", str(ROOT / "data" / "nexus.sqlite3")))
STATIC = {
    "/": ("web/index.html", "text/html; charset=utf-8"),
    "/index.html": ("web/index.html", "text/html; charset=utf-8"),
    "/style.css": ("web/style.css", "text/css; charset=utf-8"),
    "/app.js": ("web/app.js", "text/javascript; charset=utf-8"),
}
for module in ("state", "api", "domain", "ui", "views", "forms", "voice"):
    STATIC[f"/{module}.js"] = (f"web/{module}.js", "text/javascript; charset=utf-8")


WORLD_SOURCES = {
    "coingecko": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true",
    "exchange": "https://open.er-api.com/v6/latest/USD",
    "bbc": "https://feeds.bbci.co.uk/news/world/rss.xml",
}
WORLD_LIMIT = 300_000


class _FeedRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        allowed_hosts = {urlsplit(url).netloc for url in WORLD_SOURCES.values()}
        target = urlsplit(newurl)
        if target.scheme != "https" or target.netloc not in allowed_hosts:
            raise ValueError("Feed redirect is outside the approved sources")
        return super().redirect_request(request, fp, code, message, headers, newurl)


def fetch_url(url: str) -> bytes:
    """Fixed public feeds only; never a URL supplied by the browser or AI."""
    if url not in WORLD_SOURCES.values():
        raise ValueError("Unknown public feed")
    request = Request(url, headers={"User-Agent": "NEXUS-Local/0.5 public-feed-reader"})
    with build_opener(_FeedRedirect()).open(request, timeout=6) as response:
        data = response.read(WORLD_LIMIT + 1)
    if len(data) > WORLD_LIMIT:
        raise ValueError("Public feed exceeds the 300 KB limit")
    return data


def _feed_number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Invalid feed number")
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError("Invalid feed number")
    return value


def _parse_world_source(source: str, raw: bytes):
    if len(raw) > WORLD_LIMIT:
        raise ValueError("Oversized feed")
    if source == "bbc":
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("Feed document declarations are not supported")
        root = ET.fromstring(raw)
        titles = [
            " ".join("".join(node.itertext()).split())[:300]
            for node in root.findall(".//item/title")
        ]
        titles = [title for title in titles if title][:6]
        if not titles:
            raise ValueError("No RSS headlines found")
        return titles
    data = json.loads(raw)
    if source == "exchange":
        if data.get("result") != "success" or data.get("base_code") != "USD":
            raise ValueError("Unexpected exchange-rate response")
        return {
            "usd_idr": _feed_number(data["rates"]["IDR"], positive=True),
            "source_updated_at": (
                data.get("time_last_update_utc")
                if isinstance(data.get("time_last_update_utc"), str)
                else None
            ),
        }
    return {
        coin: {
            "usd": _feed_number(data[coin]["usd"], positive=True),
            "change_24h": _feed_number(data[coin]["usd_24h_change"]),
        }
        for coin in ("bitcoin", "ethereum")
    }


def fetch_world() -> dict:
    """Independent failures; missing data stays null, never sample numbers."""
    result = {
        "prices": None,
        "exchange": None,
        "headlines": [],
        "errors": [],
        "sources": {},
    }
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fields = {"coingecko": "prices", "exchange": "exchange", "bbc": "headlines"}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            source: executor.submit(fetch_url, url)
            for source, url in WORLD_SOURCES.items()
        }
        for source, future in futures.items():
            try:
                result[fields[source]] = _parse_world_source(source, future.result())
                result["sources"][source] = {
                    "status": "available",
                    "checked_at": checked,
                }
            except Exception as exc:
                result["sources"][source] = {
                    "status": "unavailable",
                    "checked_at": checked,
                }
                result["errors"].append(
                    {
                        "source": source,
                        "message": "Source unavailable",
                        "code": type(exc).__name__,
                    }
                )
    available = sum(
        item["status"] == "available" for item in result["sources"].values()
    )
    result.update(
        status="LIVE" if available == 3 else "PARTIAL" if available else "OFFLINE",
        fetched_at=checked,
        cache_seconds=300 if available else 30,
    )
    return result


def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def make_ics(events: list[dict], workspace_id="osis") -> bytes:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//NEXUS OSIS//Local Event Export//EN",
        "CALSCALE:GREGORIAN",
    ]
    for e in events:
        day = e["day"].replace("-", "")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:nexus-{workspace_id}-{e['id']}@localhost",
                f"DTSTAMP:{dtstamp}",
            ]
        )
        if e["time"]:
            lines.append(f"DTSTART:{day}T{e['time'].replace(':', '')}00")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{day}")
        lines.extend(
            [
                f"SUMMARY:{ics_escape(e['title'])}",
                f"LOCATION:{ics_escape(e['location'])}",
                f"DESCRIPTION:{ics_escape(e['details'])}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def handler_factory(
    base_store: Store, port: int, *, registry=None, allow_ai=False, demo=False
):
    provider_observations = {}
    observations_lock = threading.Lock()
    world_cache = {"data": None, "until": 0.0}
    world_lock = threading.Lock()

    def cached_world():
        with world_lock:
            if world_cache["data"] is None or time.monotonic() >= world_cache["until"]:
                payload = fetch_world()
                world_cache.update(
                    data=payload, until=time.monotonic() + payload["cache_seconds"]
                )
            return world_cache["data"]

    class Handler(BaseHTTPRequestHandler):
        server_version = "NEXUS/0.5"

        def log_message(self, format, *args):
            # Avoid logging sensitive commands or meeting-note content.
            pass

        def send_bytes(self, data: bytes, content_type: str, filename: str = ""):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                csp_for(data, content_type),
            )
            if filename:
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{filename}"'
                )
            self.end_headers()
            self.wfile.write(data)

        def host_is_local(self) -> bool:
            # HTTP Host check limits DNS-rebinding style requests. This is not user authentication.
            actual_port = self.server.server_port
            return self.headers.get("Host", "") in (
                f"127.0.0.1:{actual_port}",
                f"localhost:{actual_port}",
            )

        def json_response(self, obj: dict, code=200):
            data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def scoped_store(self):
            values = parse_qs(urlsplit(self.path).query, keep_blank_values=True).get(
                "workspace", [base_store.workspace_id]
            )
            if len(values) != 1:
                raise ValueError("Choose one workspace")
            if registry is not None:
                return registry.store(values[0])
            if values[0] != base_store.workspace_id:
                raise ValueError("Unknown workspace")
            return base_store

        def do_GET(self):
            try:
                self.get_request()
            except Exception as exc:
                logging.error("NEXUS read failed: %s", type(exc).__name__)
                self.json_response(
                    {"error": "Internal error. Refresh your workspace."}, code=500
                )

        def get_request(self):
            if not self.host_is_local():
                self.json_response({"error": "Untrusted host"}, code=403)
                return
            route = urlsplit(self.path).path
            if route in STATIC:
                location, content_type = STATIC[route]
                self.send_bytes((ROOT / location).read_bytes(), content_type)
                return
            try:
                store = self.scoped_store()
            except PermissionError as exc:
                self.json_response({"error": str(exc)}, code=403)
                return
            except ValueError as exc:
                self.json_response({"error": str(exc)}, code=400)
                return
            if route == "/api/world":
                store.require("read")
                self.json_response(cached_world())
                return
            try:
                extended = get_data(
                    store,
                    route,
                    parse_qs(urlsplit(self.path).query, keep_blank_values=True),
                )
            except LookupError as exc:
                self.json_response({"error": str(exc)}, code=404)
                return
            except ValueError as exc:
                self.json_response({"error": str(exc)}, code=400)
                return
            if extended is not None:
                self.json_response(extended)
                return
            if route == "/api/workspaces":
                self.json_response(
                    {
                        "workspaces": (
                            registry.list()
                            if registry
                            else [
                                {
                                    "id": store.workspace_id,
                                    "label": store.workspace_id.upper(),
                                    "domain": "school",
                                    "capabilities": sorted(store.capabilities),
                                }
                            ]
                        )
                    }
                )
                return
            if route == "/api/search":
                try:
                    query = parse_qs(urlsplit(self.path).query).get("q", [""])[0]
                    self.json_response(store.search(query))
                except ValueError as exc:
                    self.json_response({"error": str(exc)}, code=400)
                return
            if route == "/api/state":
                state = store.state()
                state["timezone"] = configured_timezone()
                state["demo"] = demo
                state["capabilities"] = sorted(store.capabilities)
                configured = bool(
                    allow_ai
                    and "ai" in store.capabilities
                    and os.environ.get("OPENAI_API_KEY")
                )
                with observations_lock:
                    observation = dict(
                        provider_observations.get(store.workspace_id, {})
                    )
                state["system"] = {
                    "version": "0.5 development",
                    "local": "online",
                    "ai": (
                        observation.get("status", "configured")
                        if configured
                        else "disabled"
                    ),
                    "ai_checked_at": observation.get("at"),
                    "model": (
                        os.getenv("NEXUS_MODEL", "gpt-4.1-mini") if configured else None
                    ),
                }
                state["mode"] = (
                    "Demo · temporary sample records"
                    if demo
                    else (
                        "AI + local commands"
                        if allow_ai
                        and "ai" in store.capabilities
                        and os.environ.get("OPENAI_API_KEY")
                        else "Private offline commands"
                    )
                )
                self.json_response(state)
                return
            if (
                route in {"/api/backup", "/api/calendar.ics"}
                and "export" not in store.capabilities
            ):
                self.json_response(
                    {"error": "Workspace permission required: export"}, code=403
                )
                return
            if route == "/api/backup":
                self.send_bytes(
                    json.dumps(store.export(), indent=2, ensure_ascii=False).encode(
                        "utf-8"
                    ),
                    "application/json; charset=utf-8",
                    f"nexus-{store.workspace_id}-backup.json",
                )
                return
            if route == "/api/calendar.ics":
                self.send_bytes(
                    make_ics(store.state()["events"], store.workspace_id),
                    "text/calendar; charset=utf-8",
                    f"nexus-{store.workspace_id}-calendar.ics",
                )
                return
            if route == "/api/help":
                self.json_response({"message": HELP})
                return
            self.json_response({"error": "Not found"}, code=404)

        def do_POST(self):
            if not self.host_is_local():
                self.json_response({"error": "Untrusted host"}, code=403)
                return
            route = urlsplit(self.path).path
            # Defense against other web pages making requests to localhost.
            origin = self.headers.get("Origin")
            if origin and origin not in (
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            ):
                self.json_response({"error": "Origin blocked"}, code=403)
                return
            if (
                self.headers.get("X-NEXUS-Local") != "1"
                or self.headers.get("Content-Type", "").split(";")[0]
                != "application/json"
            ):
                self.json_response(
                    {"error": "Local UI JSON request required"}, code=403
                )
                return
            try:
                store = self.scoped_store()
                coordinator = Coordinator(store, allow_ai=allow_ai)
                length = int(self.headers.get("Content-Length", "0"))
                if not (1 <= length <= (64000 if route == "/api/propose" else 16000)):
                    raise ValueError("Request too large or empty.")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object.")
                if route in {"/api/chat", "/api/commands"}:
                    result = coordinator.chat(data.get("message", ""))
                    if result.get("provider_status") in {
                        "verified",
                        "error",
                        "unavailable",
                    }:
                        with observations_lock:
                            provider_observations[store.workspace_id] = {
                                "status": (
                                    "verified"
                                    if result["provider_status"] == "verified"
                                    else "error"
                                ),
                                "at": datetime.now(timezone.utc).isoformat(
                                    timespec="seconds"
                                ),
                            }
                elif route == "/api/propose":
                    item = store.propose(data.get("name"), data.get("args"))
                    result = coordinator.report(
                        {
                            "message": "Proposal prepared. Review the exact values before approving.",
                            "pending": item,
                        }
                    )
                elif route == "/api/decide":
                    action_id = data.get("id")
                    if not isinstance(action_id, str) or len(action_id) > 128:
                        raise ValueError("Invalid action ID")
                    approve = data.get("approve")
                    if not isinstance(approve, bool):
                        raise ValueError("Approval must be true or false")
                    result_text = store.decide(action_id, approve)
                    if "propose" in store.capabilities:
                        store.record("assistant", result_text)
                    result = {
                        "message": result_text,
                        "outcome": store.approval_status(action_id),
                        "workspace": store.workspace_id,
                    }
                else:
                    self.json_response({"error": "Not found"}, code=404)
                    return
                self.json_response(result)
            except PermissionError as exc:
                self.json_response({"error": str(exc)}, code=403)
            except (ValueError, json.JSONDecodeError) as exc:
                self.json_response({"error": str(exc)}, code=400)
            except Exception as exc:
                logging.error("NEXUS request failed: %s", type(exc).__name__)
                self.json_response(
                    {
                        "error": "Internal error. No successful action is confirmed; refresh your workspace."
                    },
                    code=500,
                )

    return Handler


def cli(store: Store, *, allow_ai=False):
    assistant = Coordinator(store, allow_ai=allow_ai)
    print("\nNEXUS Core v0.5 — private local command center")
    print(
        "Type /help for commands. Type /quit to exit. Approval is required for every change.\n"
    )
    while True:
        try:
            command = input("YOU > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNEXUS offline.")
            break
        if command.lower() in ("/quit", "/exit"):
            break
        if not command:
            continue
        if command.lower() == "/plan":
            print("Enter up to five write commands, then a blank line:")
            lines = []
            try:
                while len(lines) < 5:
                    line = input("STEP > ").strip()
                    if not line:
                        break
                    lines.append(line)
            except (EOFError, KeyboardInterrupt):
                print("Plan entry cancelled.")
                continue
            command += "\n" + "\n".join(lines)
        result = assistant.chat(command)
        print("\nNEXUS >", result["message"])
        pending = result.get("pending")
        if pending:
            print("\nREQUIRES APPROVAL:", pending["description"])
            print(json.dumps(pending["args"], ensure_ascii=False, indent=2))
            answer = input("Approve? Type YES to confirm: ").strip()
            try:
                print("NEXUS >", store.decide(pending["id"], answer == "YES"))
            except ValueError as exc:
                print("NEXUS >", exc)
        print()


def main():
    parser = argparse.ArgumentParser(description="NEXUS — local personal AI core")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use invented temporary records; discarded on exit, AI disabled",
    )
    parser.add_argument(
        "--workspace",
        default="osis",
        choices=[
            "osis",
            "personal",
            "academic",
            "research",
            "coding",
            "finance",
            "atlas",
        ],
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Separate workspace database directory",
    )
    parser.add_argument(
        "--enable-ai",
        action="store_true",
        help="Opt in to sending active-workspace context to OpenAI",
    )
    parser.add_argument("--cli", action="store_true", help="Text-only terminal mode")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open your browser automatically",
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Local web port (default 8765)"
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB, help="Path to SQLite database"
    )
    args = parser.parse_args()
    if not args.cli and not 1024 <= args.port <= 65535:
        parser.error("Port must be 1024..65535")
    if args.demo:
        if args.enable_ai:
            parser.error("Demo mode is offline; omit --enable-ai")
        with tempfile.TemporaryDirectory(prefix="nexus-demo-") as directory:
            args.db = Path(directory) / "osis.sqlite3"
            args.workspace_root = Path(directory) / "workspaces"
            print("DEMO: invented temporary records; changes are discarded on exit.")
            run(args)
    else:
        run(args)


def run(args):
    with WorkspaceRegistry(
        args.db,
        args.workspace_root or args.db.parent / "workspaces",
        runtime_locks=True,
    ) as registry:
        run_workspace(args, registry)


def run_workspace(args, registry):
    if args.demo:
        from nexus.demo import seed_demo

        seed_demo(registry)
    store = registry.store(args.workspace)
    if args.cli:
        cli(store, allow_ai=args.enable_ai)
        return
    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", args.port),
            handler_factory(
                store,
                args.port,
                registry=registry,
                allow_ai=args.enable_ai,
                demo=args.demo,
            ),
        )
    except OSError as exc:
        sys.exit(f"Could not start NEXUS on port {args.port}: {exc}. Try --port 8766")
    url = f"http://127.0.0.1:{args.port}"
    print("\nNEXUS Core v0.5")
    print("Local dashboard:", url)
    print("Local records:", store.path)
    print(
        "Brain mode:",
        (
            "Optional AI enabled"
            if args.enable_ai and os.environ.get("OPENAI_API_KEY")
            else "Offline command mode"
        ),
    )
    print("To stop: press Control + C\n")
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nNEXUS stopped. Data remains on disk.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
