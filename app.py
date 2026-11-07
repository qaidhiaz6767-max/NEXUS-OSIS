"""Local-only HTTP and CLI entry point for NEXUS OSIS.
Start: python3 app.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import tempfile
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from core import Coordinator, Store, HELP
from nexus.validation import configured_timezone
from nexus.workspaces import WorkspaceRegistry

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = Path(os.environ.get("NEXUS_DB", str(ROOT / "data" / "nexus.sqlite3")))
STATIC = {"/": ("web/index.html", "text/html; charset=utf-8"),
          "/index.html": ("web/index.html", "text/html; charset=utf-8"),
          "/style.css": ("web/style.css", "text/css; charset=utf-8"),
          "/app.js": ("web/app.js", "text/javascript; charset=utf-8")}
for module in ("state", "api", "domain", "ui", "views", "forms", "voice"):
    STATIC[f"/{module}.js"] = (f"web/{module}.js", "text/javascript; charset=utf-8")


def ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def make_ics(events: list[dict], workspace_id="osis") -> bytes:
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NEXUS OSIS//Local Event Export//EN", "CALSCALE:GREGORIAN"]
    for e in events:
        day = e["day"].replace("-", "")
        lines.extend(["BEGIN:VEVENT", f"UID:nexus-{workspace_id}-{e['id']}@localhost", f"DTSTAMP:{dtstamp}"])
        if e["time"]:
            lines.append(f"DTSTART:{day}T{e['time'].replace(':', '')}00")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{day}")
        lines.extend([f"SUMMARY:{ics_escape(e['title'])}",
                      f"LOCATION:{ics_escape(e['location'])}",
                      f"DESCRIPTION:{ics_escape(e['details'])}", "END:VEVENT"])
    lines.append("END:VCALENDAR")
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def handler_factory(base_store: Store, port: int, *, registry=None, allow_ai=False, demo=False):
    provider_observations = {}
    observations_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "NEXUS/0.4"

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
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def host_is_local(self) -> bool:
            # HTTP Host check limits DNS-rebinding style requests. This is not user authentication.
            actual_port = self.server.server_port
            return self.headers.get("Host", "") in (
                f"127.0.0.1:{actual_port}", f"localhost:{actual_port}"
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
            values = parse_qs(urlsplit(self.path).query, keep_blank_values=True).get("workspace", [base_store.workspace_id])
            if len(values) != 1:
                raise ValueError("Choose one workspace")
            if registry is not None:
                return registry.store(values[0])
            if values[0] != base_store.workspace_id:
                raise ValueError("Unknown workspace")
            return base_store

        def do_GET(self):
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
            if route == "/api/workspaces":
                self.json_response({"workspaces": registry.list() if registry else [
                    {"id": store.workspace_id, "label": store.workspace_id.upper(),
                     "domain": "school", "capabilities": sorted(store.capabilities)}]})
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
                configured = bool(allow_ai and "ai" in store.capabilities and os.environ.get("OPENAI_API_KEY"))
                with observations_lock:
                    observation = dict(provider_observations.get(store.workspace_id, {}))
                state["system"] = {"version": "0.4 development", "local": "online",
                                   "ai": observation.get("status", "configured") if configured else "disabled",
                                   "ai_checked_at": observation.get("at"),
                                   "model": os.getenv("NEXUS_MODEL", "gpt-4.1-mini") if configured else None}
                state["mode"] = "Demo · temporary sample records" if demo else "AI + local commands" if allow_ai and "ai" in store.capabilities and os.environ.get("OPENAI_API_KEY") else "Private offline commands"
                self.json_response(state)
                return
            if route in {"/api/backup", "/api/calendar.ics"} and "export" not in store.capabilities:
                self.json_response({"error": "Workspace permission required: export"}, code=403)
                return
            if route == "/api/backup":
                self.send_bytes(json.dumps(store.export(), indent=2, ensure_ascii=False).encode("utf-8"),
                                "application/json; charset=utf-8", f"nexus-{store.workspace_id}-backup.json")
                return
            if route == "/api/calendar.ics":
                self.send_bytes(make_ics(store.state()["events"], store.workspace_id), "text/calendar; charset=utf-8", f"nexus-{store.workspace_id}-calendar.ics")
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
                f"http://localhost:{self.server.server_port}"
            ):
                self.json_response({"error": "Origin blocked"}, code=403)
                return
            if self.headers.get("X-NEXUS-Local") != "1" or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.json_response({"error": "Local UI JSON request required"}, code=403)
                return
            try:
                store = self.scoped_store()
                coordinator = Coordinator(store, allow_ai=allow_ai)
                length = int(self.headers.get("Content-Length", "0"))
                if not (1 <= length <= 16000):
                    raise ValueError("Request too large or empty.")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object.")
                if route == "/api/chat":
                    result = coordinator.chat(data.get("message", ""))
                    if result.get("provider_status") in {"verified", "error", "unavailable"}:
                        with observations_lock:
                            provider_observations[store.workspace_id] = {
                                "status": "verified" if result["provider_status"] == "verified" else "error",
                                "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                elif route == "/api/propose":
                    item = store.propose(data.get("name"), data.get("args"))
                    result = coordinator.report({"message": "Proposal prepared. Review the exact values before approving.", "pending": item})
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
                    result = {"message": result_text, "outcome": store.approval_status(action_id), "workspace": store.workspace_id}
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
                self.json_response({"error": "Internal error. No successful action is confirmed; refresh your workspace."}, code=500)

    return Handler


def cli(store: Store, *, allow_ai=False):
    assistant = Coordinator(store, allow_ai=allow_ai)
    print("\nNEXUS Core v0.4 — private local command center")
    print("Type /help for commands. Type /quit to exit. Approval is required for every change.\n")
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
    parser.add_argument("--demo", action="store_true", help="Use invented temporary records; discarded on exit, AI disabled")
    parser.add_argument("--workspace", default="osis", choices=["osis", "personal", "academic", "research", "coding", "finance", "atlas"])
    parser.add_argument("--workspace-root", type=Path, default=None, help="Separate workspace database directory")
    parser.add_argument("--enable-ai", action="store_true", help="Opt in to sending active-workspace context to OpenAI")
    parser.add_argument("--cli", action="store_true", help="Text-only terminal mode")
    parser.add_argument("--no-browser", action="store_true", help="Don't open your browser automatically")
    parser.add_argument("--port", type=int, default=8765, help="Local web port (default 8765)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to SQLite database")
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
    registry = WorkspaceRegistry(args.db, args.workspace_root or args.db.parent / "workspaces")
    if args.demo:
        from nexus.demo import seed_demo
        seed_demo(registry)
    store = registry.store(args.workspace)
    if args.cli:
        cli(store, allow_ai=args.enable_ai)
        return
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_factory(store, args.port, registry=registry, allow_ai=args.enable_ai, demo=args.demo))
    except OSError as exc:
        sys.exit(f"Could not start NEXUS on port {args.port}: {exc}. Try --port 8766")
    url = f"http://127.0.0.1:{args.port}"
    print("\nNEXUS Core v0.4")
    print("Local dashboard:", url)
    print("Local records:", store.path)
    print("Brain mode:", "Optional AI enabled" if args.enable_ai and os.environ.get("OPENAI_API_KEY") else "Offline command mode")
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
