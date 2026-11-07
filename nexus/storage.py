"""Workspace-scoped SQLite repositories and atomic approval execution."""
from __future__ import annotations
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .migrations import initialize_schema
from .permissions import CAPABILITIES, require_capability
from .validation import validate_action, action_description, clean_text, now, today_local

class Store:
    def __init__(self, db_path: str | Path, *, workspace_id="osis", capabilities=None):
        self.workspace_id = clean_text(workspace_id, "Workspace ID", 40)
        self.capabilities = frozenset(CAPABILITIES if capabilities is None else capabilities)
        self.require("read")
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass  # Keep existing database ownership and permissions intact.
        else:
            os.close(fd)
        self._init()

    def require(self, capability):
        require_capability(self.capabilities, capability)

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _init(self):
        with self._conn() as con:
            initialize_schema(con, self.workspace_id)

    @staticmethod
    def _rows(con, sql, parameters=()):
        return [dict(r) for r in con.execute(sql, parameters).fetchall()]

    def state(self) -> dict:
        self.require("read")
        with self._conn() as con:
            con.execute("BEGIN")  # One consistent snapshot for counts and record lists.
            return {
                "summary": {
                    "active_projects": con.execute("SELECT count(*) FROM projects WHERE status='active'").fetchone()[0],
                    "open_tasks": con.execute("SELECT count(*) FROM tasks WHERE status!='done'").fetchone()[0],
                    "overdue_tasks": con.execute("SELECT count(*) FROM tasks WHERE status!='done' AND due_date!='' AND due_date<?", (today_local().isoformat(),)).fetchone()[0],
                    "due_soon": con.execute("SELECT count(*) FROM tasks WHERE status!='done' AND due_date>=? AND due_date<=?", (today_local().isoformat(), (today_local()+timedelta(days=7)).isoformat())).fetchone()[0],
                    "upcoming_events": con.execute("SELECT count(*) FROM events WHERE day>=?", (today_local().isoformat(),)).fetchone()[0],
                    "pending_approvals": con.execute("SELECT count(*) FROM pending_actions WHERE status='pending' AND expires_at>?", (now(),)).fetchone()[0],
                },
                "workspace": self.workspace_id,
                "projects": self._rows(con, "SELECT * FROM projects ORDER BY id DESC LIMIT 100"),
                "tasks": self._rows(con, "SELECT * FROM tasks ORDER BY CASE status WHEN 'done' THEN 1 ELSE 0 END, CASE WHEN due_date='' THEN 1 ELSE 0 END, due_date ASC, id DESC LIMIT 250"),
                "events": self._rows(con, "SELECT * FROM events ORDER BY day ASC, time ASC LIMIT 250"),
                "notes": self._rows(con, "SELECT * FROM notes ORDER BY id DESC LIMIT 100"),
                "memories": self._rows(con, "SELECT m.*, p.source, p.created_at, p.approved_at, p.approval_id FROM memories m LEFT JOIN memory_metadata p ON m.key=p.key ORDER BY m.key LIMIT 100"),
                "pending": self._rows(con, "SELECT id, name, description, args_json, expires_at FROM pending_actions WHERE status='pending' ORDER BY created_at DESC LIMIT 30"),
                "audit": self._rows(con, "SELECT * FROM audit ORDER BY id DESC LIMIT 30"),
                "messages": self._rows(con, "SELECT * FROM messages ORDER BY id DESC LIMIT 35")[::-1],
            }

    def recent_messages(self, limit: int = 6) -> list[dict]:
        self.require("read")
        with self._conn() as con:
            return self._rows(con, "SELECT role, content FROM (SELECT * FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id", (limit,))

    def record(self, role: str, content: str):
        self.require("propose")
        if role not in ("user", "assistant"):
            raise ValueError("Invalid role")
        content = clean_text(content, "Message", 8000)
        with self._conn() as con:
            con.execute("INSERT INTO messages(at,role,content) VALUES(?,?,?)", (now(), role, content))

    def propose(self, name: str, args: dict, *, source="command") -> dict:
        self.require("propose")
        if source not in {"command", "ai"}:
            raise ValueError("Invalid proposal source")
        norm = validate_action(name, args)
        item_id = secrets.token_urlsafe(18)
        description = action_description(name, norm)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds")
        with self._conn() as con:
            con.execute("INSERT INTO pending_actions VALUES (?,?,?,?,?,?,?)",
                        (item_id, name, json.dumps(norm, ensure_ascii=False), description, "pending", now(), expires))
            con.execute("INSERT INTO pending_metadata VALUES(?,?)", (item_id, source))
            con.execute("INSERT INTO audit(at,event,detail) VALUES(?,?,?)", (now(), "proposed", description))
        return {"id": item_id, "name": name, "description": description, "args": norm, "expires_at": expires}

    def _execute(self, con, name: str, args: dict, *, source="legacy", approval_id=""):
        if name == "execute_plan":
            results = [self._execute(con, step["name"], step["args"], source=source, approval_id=approval_id)
                       for step in args["steps"]]
            return "Plan completed:\n" + "\n".join(results)
        if name == "forget":
            cur = con.execute("DELETE FROM memories WHERE key=?", (args["key"],))
            if not cur.rowcount:
                raise ValueError("Memory does not exist")
            return f"Deleted memory: {args['key']}."
        if name == "create_project":
            cur = con.execute("INSERT INTO projects(title,goal,status,created_at) VALUES(?,?,?,?)",
                              (args["title"], args["goal"], args["status"], now()))
            return f"Project #{cur.lastrowid} created."
        # The only available mutations are these explicit SQLite statements.
        if name == "create_task":
            cur = con.execute("INSERT INTO tasks(title,owner,due_date,priority,status,created_at) VALUES(?,?,?,?,'todo',?)",
                              (args["title"], args["owner"], args["due_date"], args["priority"], now()))
            return f"Task #{cur.lastrowid} created."
        if name == "set_task_status":
            cur = con.execute("UPDATE tasks SET status=? WHERE id=?", (args["status"], args["task_id"]))
            if not cur.rowcount:
                raise ValueError(f"Task #{args['task_id']} does not exist.")
            return f"Task #{args['task_id']} set to {args['status']}."
        if name == "assign_task":
            cur = con.execute("UPDATE tasks SET owner=? WHERE id=?", (args["owner"], args["task_id"]))
            if not cur.rowcount:
                raise ValueError(f"Task #{args['task_id']} does not exist.")
            return f"Task #{args['task_id']} assigned to {args['owner']}."
        if name == "create_event":
            cur = con.execute("INSERT INTO events(title,day,time,location,details,created_at) VALUES(?,?,?,?,?,?)",
                              (args["title"], args["day"], args["time"], args["location"], args["details"], now()))
            return f"Event #{cur.lastrowid} saved."
        if name == "create_note":
            cur = con.execute("INSERT INTO notes(title,body,created_at) VALUES(?,?,?)",
                              (args["title"], args["body"], now()))
            return f"Note #{cur.lastrowid} saved."
        if name == "remember":
            con.execute("INSERT INTO memories(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                        (args["key"], args["value"], now()))
            con.execute("""INSERT INTO memory_metadata VALUES(?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET source=excluded.source,
                approved_at=excluded.approved_at, approval_id=excluded.approval_id""",
                (args["key"], source, now(), now(), approval_id))
            return f"Saved memory: {args['key']}."
        raise ValueError("Unsupported action")

    def decide(self, action_id: str, approve: bool) -> str:
        self.require("approve")
        if not isinstance(approve, bool):
            raise ValueError("Approval must be true or false")
        with self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM pending_actions WHERE id=?", (action_id,)).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("Action not found or already decided.")
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
                con.execute("UPDATE pending_actions SET status='expired' WHERE id=?", (action_id,))
                con.execute("INSERT INTO audit(at,event,detail) VALUES(?,?,?)", (now(), "expired", row["description"]))
                return "The approval expired. Please request the action again."
            if not approve:
                con.execute("UPDATE pending_actions SET status='rejected' WHERE id=?", (action_id,))
                con.execute("INSERT INTO audit(at,event,detail) VALUES(?,?,?)", (now(), "rejected", row["description"]))
                return "Action cancelled. Nothing changed."
            # Revalidate persisted model/command arguments.
            args = validate_action(row["name"], json.loads(row["args_json"]))
            provenance = con.execute("SELECT source FROM pending_metadata WHERE action_id=?", (action_id,)).fetchone()
            result = self._execute(con, row["name"], args,
                                   source=provenance["source"] if provenance else "legacy",
                                   approval_id=action_id)
            con.execute("UPDATE pending_actions SET status='approved' WHERE id=?", (action_id,))
            con.execute("INSERT INTO audit(at,event,detail) VALUES(?,?,?)", (now(), "approved", row["description"]))
            return result

    def brief(self) -> str:
        state = self.state()
        tasks = [x for x in state["tasks"] if x["status"] != "done"]
        today = today_local()
        overdue = [x for x in tasks if x["due_date"] and x["due_date"] < today.isoformat()]
        soon = [x for x in tasks if x["due_date"] and today.isoformat() <= x["due_date"] <= (today + timedelta(days=7)).isoformat()]
        future_events = [e for e in state["events"] if e["day"] >= today.isoformat()][:5]
        lines = [f"{self.workspace_id.upper()} BRIEFING — {today.isoformat()}", f"Open tasks: {len(tasks)} | Overdue: {len(overdue)} | Due within 7 days: {len(soon)}"]
        if overdue:
            lines.append("\nOVERDUE: " + "; ".join(f"#{t['id']} {t['title']} ({t['owner']})" for t in overdue[:5]))
        if soon:
            lines.append("\nUPCOMING TASKS:")
            lines.extend(f"• #{t['id']} {t['title']} — {t['owner']} — {t['due_date']}" for t in soon[:8])
        if future_events:
            lines.append("\nNEXT EVENTS:")
            lines.extend(f"• {e['day']} {e['time']} — {e['title']}" for e in future_events)
        if not tasks and not future_events:
            lines.append("No active tasks or upcoming events yet. Add one using /task add or /event add.")
        return "\n".join(lines)

    def export(self) -> dict:
        self.require("export")
        self.require("read")
        # Full record snapshot, independent of the dashboard's pagination limits.
        # History and pending approvals remain private and are intentionally omitted.
        with self._conn() as con:
            data = {table: self._rows(con, f"SELECT * FROM {table}")
                    for table in ("tasks", "events", "notes", "projects", "audit")}
            data["memories"] = self._rows(con, "SELECT m.*, p.source, p.created_at, p.approved_at, p.approval_id FROM memories m LEFT JOIN memory_metadata p ON m.key=p.key ORDER BY m.key")
        return {"format": "nexus-osis-v1" if self.workspace_id == "osis" else "nexus-core-v1",
                "workspace": self.workspace_id, "exported_at": now(), **data}

    def search(self, query: str) -> dict:
        """Bounded literal substring search across workspace facts/projects/history."""
        self.require("read")
        query = clean_text(query, "Search query", 200)
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with self._conn() as con:
            return {
                "facts": self._rows(con, "SELECT m.*, p.source, p.created_at, p.approved_at, p.approval_id FROM memories m LEFT JOIN memory_metadata p ON m.key=p.key WHERE m.key LIKE ? ESCAPE '\\' OR m.value LIKE ? ESCAPE '\\' ORDER BY m.updated_at DESC LIMIT 50", (pattern, pattern)),
                "projects": self._rows(con, "SELECT * FROM projects WHERE title LIKE ? ESCAPE '\\' OR goal LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 50", (pattern, pattern)),
                "history": self._rows(con, "SELECT * FROM messages WHERE content LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 50", (pattern,)),
                "notes": self._rows(con, "SELECT * FROM notes WHERE title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 50", (pattern, pattern)),
            }

    def log_event(self, event: str, detail: str):
        """Only host code calls this; error callers supply categories, not exception text."""
        self.require("propose")
        with self._conn() as con:
            con.execute("INSERT INTO audit(at,event,detail) VALUES(?,?,?)", (now(), event, detail))

    def approval_status(self, action_id: str) -> str:
        self.require("read")
        with self._conn() as con:
            row = con.execute("SELECT status FROM pending_actions WHERE id=?", (action_id,)).fetchone()
            if row is None:
                raise ValueError("Action not found")
            return row["status"]
