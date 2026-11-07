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
from .action_schemas import EXECUTIVE_ACTIONS
from .planning import fingerprints, verify_fingerprints, plan_transition, transition
from .validation import (
    validate_action,
    action_description,
    clean_text,
    now,
    today_local,
)


class Store:
    def __init__(self, db_path: str | Path, *, workspace_id="osis", capabilities=None):
        self.workspace_id = clean_text(workspace_id, "Workspace ID", 40)
        self.capabilities = frozenset(
            CAPABILITIES if capabilities is None else capabilities
        )
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
        rows = [dict(r) for r in con.execute(sql, parameters).fetchall()]
        for row in rows:
            if "valid_until" in row:
                row["stale"] = bool(
                    row["valid_until"]
                    and row["valid_until"] < today_local().isoformat()
                )
        return rows

    def state(self) -> dict:
        self.require("read")
        with self._conn() as con:
            con.execute("BEGIN")  # One consistent snapshot for counts and record lists.
            return {
                "summary": {
                    "active_projects": con.execute(
                        "SELECT count(*) FROM projects WHERE status='active'"
                    ).fetchone()[0],
                    "open_tasks": con.execute(
                        "SELECT count(*) FROM tasks WHERE status!='done'"
                    ).fetchone()[0],
                    "overdue_tasks": con.execute(
                        "SELECT count(*) FROM tasks WHERE status!='done' AND due_date!='' AND due_date<?",
                        (today_local().isoformat(),),
                    ).fetchone()[0],
                    "due_soon": con.execute(
                        "SELECT count(*) FROM tasks WHERE status!='done' AND due_date>=? AND due_date<=?",
                        (
                            today_local().isoformat(),
                            (today_local() + timedelta(days=7)).isoformat(),
                        ),
                    ).fetchone()[0],
                    "upcoming_events": con.execute(
                        "SELECT count(*) FROM events WHERE day>=?",
                        (today_local().isoformat(),),
                    ).fetchone()[0],
                    "pending_approvals": con.execute(
                        "SELECT count(*) FROM pending_actions WHERE status='pending' AND expires_at>?",
                        (now(),),
                    ).fetchone()[0],
                },
                "meetings": self._rows(
                    con, "SELECT * FROM meetings ORDER BY id DESC LIMIT 100"
                ),
                "decisions": self._rows(
                    con, "SELECT * FROM decisions ORDER BY id DESC LIMIT 100"
                ),
                "milestones": self._rows(
                    con, "SELECT * FROM milestones ORDER BY id DESC LIMIT 100"
                ),
                "task_dependencies": self._rows(
                    con,
                    "SELECT * FROM task_dependencies ORDER BY task_id,depends_on LIMIT 1000",
                ),
                "workspace": self.workspace_id,
                "projects": self._rows(
                    con,
                    "SELECT p.*,d.owner,d.target_date,d.updated_at FROM projects p LEFT JOIN project_details d ON p.id=d.project_id ORDER BY p.id DESC LIMIT 100",
                ),
                "tasks": self._rows(
                    con,
                    "SELECT t.*,d.description,d.project_id,d.milestone_id,d.completed_at,d.follow_up_context FROM tasks t LEFT JOIN task_details d ON d.task_id=t.id ORDER BY CASE status WHEN 'done' THEN 1 ELSE 0 END, CASE WHEN due_date='' THEN 1 ELSE 0 END, due_date ASC, t.id DESC LIMIT 250",
                ),
                "events": self._rows(
                    con, "SELECT * FROM events ORDER BY day ASC, time ASC LIMIT 250"
                ),
                "notes": self._rows(
                    con, "SELECT * FROM notes ORDER BY id DESC LIMIT 100"
                ),
                "memories": self._rows(
                    con,
                    "SELECT m.*, p.source, p.created_at, p.approved_at, p.approval_id,d.category,d.source_ref,d.valid_until,d.confirmation FROM memories m LEFT JOIN memory_metadata p ON m.key=p.key LEFT JOIN memory_details d ON m.key=d.key ORDER BY m.key LIMIT 100",
                ),
                "pending": self._rows(
                    con,
                    "SELECT id, name, description, args_json, expires_at FROM pending_actions WHERE status='pending' ORDER BY created_at DESC LIMIT 30",
                ),
                "audit": self._rows(
                    con, "SELECT * FROM audit ORDER BY id DESC LIMIT 30"
                ),
                "messages": self._rows(
                    con, "SELECT * FROM messages ORDER BY id DESC LIMIT 35"
                )[::-1],
            }

    def recent_messages(self, limit: int = 6) -> list[dict]:
        self.require("read")
        with self._conn() as con:
            return self._rows(
                con,
                "SELECT role, content FROM (SELECT * FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id",
                (limit,),
            )

    def record(self, role: str, content: str):
        self.require("propose")
        if role not in ("user", "assistant"):
            raise ValueError("Invalid role")
        content = clean_text(content, "Message", 8000)
        with self._conn() as con:
            con.execute(
                "INSERT INTO messages(at,role,content) VALUES(?,?,?)",
                (now(), role, content),
            )

    def propose(self, name: str, args: dict, *, source="command") -> dict:
        self.require("propose")
        if source not in {"command", "ai"}:
            raise ValueError("Invalid proposal source")
        norm = validate_action(name, args)
        item_id = secrets.token_urlsafe(18)
        description = action_description(name, norm)
        expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(
            timespec="seconds"
        )
        with self._conn() as con:
            confirmation_tables = {
                "approve_decision": ("decisions", "decision_id"),
                "confirm_meeting_action": ("meeting_actions", "action_item_id"),
                "create_followup_task": ("meeting_actions", "action_item_id"),
            }
            operations = (
                norm["steps"]
                if name == "execute_plan"
                else [{"name": name, "args": norm}]
            )
            for operation in operations:
                if operation["name"] in confirmation_tables:
                    from .executive import require_record

                    table, key = confirmation_tables[operation["name"]]
                    require_record(con, table, operation["args"][key])
            con.execute(
                "INSERT INTO pending_actions VALUES (?,?,?,?,?,?,?)",
                (
                    item_id,
                    name,
                    json.dumps(norm, ensure_ascii=False),
                    description,
                    "pending",
                    now(),
                    expires,
                ),
            )
            con.execute("INSERT INTO pending_metadata VALUES(?,?)", (item_id, source))
            con.execute(
                "INSERT INTO pending_context VALUES(?,?)",
                (
                    item_id,
                    json.dumps(fingerprints(con, name, norm), ensure_ascii=False),
                ),
            )
            con.execute(
                "INSERT INTO plan_records(id,objective,status,created_at,updated_at) VALUES(?,?,'awaiting_approval',?,?)",
                (item_id, description, now(), now()),
            )
            from .memory import proposal_diagnostics

            diagnostics = proposal_diagnostics(con, name, norm)
            con.execute(
                "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
                (now(), "proposed", description),
            )
        return {
            "id": item_id,
            "name": name,
            "description": description,
            "args": norm,
            "expires_at": expires,
            "diagnostics": diagnostics,
        }

    def _execute(self, con, name: str, args: dict, *, source="legacy", approval_id=""):
        if name in EXECUTIVE_ACTIONS:
            from .executive import execute

            return execute(con, name, args, approval_id)
        if name == "execute_plan":
            results = [
                self._execute(
                    con,
                    step["name"],
                    step["args"],
                    source=source,
                    approval_id=approval_id,
                )
                for step in args["steps"]
            ]
            if len(args["steps"]) > 1:
                con.execute(
                    "UPDATE conversation_references SET last_task_id=NULL WHERE singleton=1"
                )
            return "Plan completed:\n" + "\n".join(results)
        if name == "forget":
            cur = con.execute("DELETE FROM memories WHERE key=?", (args["key"],))
            if not cur.rowcount:
                raise ValueError("Memory does not exist")
            return f"Deleted memory: {args['key']}."
        if name == "create_project":
            cur = con.execute(
                "INSERT INTO projects(title,goal,status,created_at) VALUES(?,?,?,?)",
                (args["title"], args["goal"], args["status"], now()),
            )
            con.execute(
                "INSERT INTO project_details VALUES(?,?,?,?)",
                (cur.lastrowid, args["owner"], args["target_date"], now()),
            )
            con.execute(
                "UPDATE conversation_references SET last_project_id=? WHERE singleton=1",
                (cur.lastrowid,),
            )
            return f"Project #{cur.lastrowid} created."
        # The only available mutations are these explicit SQLite statements.
        if name == "create_task":
            cur = con.execute(
                "INSERT INTO tasks(title,owner,due_date,priority,status,created_at) VALUES(?,?,?,?,'todo',?)",
                (
                    args["title"],
                    args["owner"],
                    args["due_date"],
                    args["priority"],
                    now(),
                ),
            )
            from .executive import link_task

            link_task(
                con,
                cur.lastrowid,
                args["project_id"],
                args["milestone_id"],
                args["description"],
            )
            con.execute(
                "UPDATE conversation_references SET last_task_id=? WHERE singleton=1",
                (cur.lastrowid,),
            )
            return f"Task #{cur.lastrowid} created."
        if name == "set_task_status":
            prior = con.execute(
                "SELECT status FROM tasks WHERE id=?", (args["task_id"],)
            ).fetchone()
            if (
                args["status"] in {"doing", "done"}
                and con.execute(
                    "SELECT 1 FROM task_dependencies d JOIN tasks t ON d.depends_on=t.id WHERE d.task_id=? AND t.status!='done' LIMIT 1",
                    (args["task_id"],),
                ).fetchone()
            ):
                raise ValueError("Complete the prerequisite tasks first.")
            cur = con.execute(
                "UPDATE tasks SET status=? WHERE id=?",
                (args["status"], args["task_id"]),
            )
            if not cur.rowcount:
                raise ValueError(f"Task #{args['task_id']} does not exist.")
            con.execute(
                "INSERT OR IGNORE INTO task_details(task_id) VALUES(?)",
                (args["task_id"],),
            )
            if args["status"] == "done" and prior["status"] != "done":
                con.execute(
                    "UPDATE task_details SET completed_at=? WHERE task_id=?",
                    (now(), args["task_id"]),
                )
            if args["status"] != "done":
                con.execute(
                    "UPDATE task_details SET completed_at=NULL WHERE task_id=?",
                    (args["task_id"],),
                )
            con.execute(
                "UPDATE conversation_references SET last_task_id=? WHERE singleton=1",
                (args["task_id"],),
            )
            return f"Task #{args['task_id']} set to {args['status']}."
        if name == "assign_task":
            cur = con.execute(
                "UPDATE tasks SET owner=? WHERE id=?", (args["owner"], args["task_id"])
            )
            if not cur.rowcount:
                raise ValueError(f"Task #{args['task_id']} does not exist.")
            con.execute(
                "UPDATE conversation_references SET last_task_id=? WHERE singleton=1",
                (args["task_id"],),
            )
            return f"Task #{args['task_id']} assigned to {args['owner']}."
        if name == "create_event":
            cur = con.execute(
                "INSERT INTO events(title,day,time,location,details,created_at) VALUES(?,?,?,?,?,?)",
                (
                    args["title"],
                    args["day"],
                    args["time"],
                    args["location"],
                    args["details"],
                    now(),
                ),
            )
            return f"Event #{cur.lastrowid} saved."
        if name == "create_note":
            cur = con.execute(
                "INSERT INTO notes(title,body,created_at) VALUES(?,?,?)",
                (args["title"], args["body"], now()),
            )
            return f"Note #{cur.lastrowid} saved."
        if name == "remember":
            con.execute(
                "INSERT INTO memories(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (args["key"], args["value"], now()),
            )
            con.execute(
                """INSERT INTO memory_metadata VALUES(?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET source=excluded.source,
                approved_at=excluded.approved_at, approval_id=excluded.approval_id""",
                (args["key"], source, now(), now(), approval_id),
            )
            con.execute(
                """INSERT INTO memory_details VALUES(?,?,?,?,'confirmed') ON CONFLICT(key) DO UPDATE SET
                category=excluded.category,source_ref=excluded.source_ref,valid_until=excluded.valid_until,confirmation='confirmed'""",
                (
                    args["key"],
                    args["category"],
                    args["source_ref"],
                    args["valid_until"],
                ),
            )
            return f"Saved memory: {args['key']}."
        raise ValueError("Unsupported action")

    def decide(self, action_id: str, approve: bool) -> str:
        self.require("approve")
        if not isinstance(approve, bool):
            raise ValueError("Approval must be true or false")
        try:
            return self._decide(action_id, approve)
        except (ValueError, sqlite3.Error) as exc:
            # All business writes rolled back. Keep a separately committed failure category.
            with self._conn() as con:
                pending = con.execute(
                    "SELECT status FROM pending_actions WHERE id=?", (action_id,)
                ).fetchone()
                if pending and pending[0] == "pending":
                    plan_transition(
                        con,
                        action_id,
                        "failed",
                        result={
                            "verified": False,
                            "rolled_back": True,
                            "message": (
                                str(exc)
                                if isinstance(exc, ValueError)
                                else "Database operation failed."
                            ),
                        },
                        error=type(exc).__name__,
                    )
                    con.execute(
                        "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
                        (now(), "execution_failed", type(exc).__name__),
                    )
            raise

    def _decide(self, action_id: str, approve: bool) -> str:
        self.require("approve")
        if not isinstance(approve, bool):
            raise ValueError("Approval must be true or false")
        with self._conn() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM pending_actions WHERE id=?", (action_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("Action not found or already decided.")
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
                con.execute(
                    "UPDATE pending_actions SET status='expired' WHERE id=?",
                    (action_id,),
                )
                con.execute(
                    "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
                    (now(), "expired", row["description"]),
                )
                plan_transition(con, action_id, "cancelled", error="approval_expired")
                return "The approval expired. Please request the action again."
            if not approve:
                con.execute(
                    "UPDATE pending_actions SET status='rejected' WHERE id=?",
                    (action_id,),
                )
                con.execute(
                    "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
                    (now(), "rejected", row["description"]),
                )
                plan_transition(con, action_id, "cancelled")
                return "Action cancelled. Nothing changed."
            verify_fingerprints(con, action_id)
            plan_transition(con, action_id, "executing")
            # Revalidate persisted model/command arguments.
            args = validate_action(row["name"], json.loads(row["args_json"]))
            provenance = con.execute(
                "SELECT source FROM pending_metadata WHERE action_id=?", (action_id,)
            ).fetchone()
            result = self._execute(
                con,
                row["name"],
                args,
                source=provenance["source"] if provenance else "legacy",
                approval_id=action_id,
            )
            con.execute(
                "UPDATE pending_actions SET status='approved' WHERE id=?", (action_id,)
            )
            con.execute(
                "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
                (now(), "approved", row["description"]),
            )
            plan_transition(
                con,
                action_id,
                "completed",
                result={"verified": True, "message": result, "atomic": True},
            )
            return result

    def brief(self) -> str:
        from .briefing import build_briefing

        return build_briefing(self)["message"]

    def export(self) -> dict:
        self.require("export")
        self.require("read")
        # Full record snapshot, independent of the dashboard's pagination limits.
        # History and pending approvals remain private and are intentionally omitted.
        with self._conn() as con:
            con.execute("BEGIN")
            data = {
                table: self._rows(con, f"SELECT * FROM {table}")
                for table in (
                    "tasks",
                    "events",
                    "notes",
                    "projects",
                    "audit",
                    "project_details",
                    "task_details",
                    "milestones",
                    "task_dependencies",
                    "meetings",
                    "decisions",
                    "meeting_actions",
                )
            }
            data["memories"] = self._rows(
                con,
                "SELECT m.*, p.source, p.created_at, p.approved_at, p.approval_id,d.category,d.source_ref,d.valid_until,d.confirmation FROM memories m LEFT JOIN memory_metadata p ON m.key=p.key LEFT JOIN memory_details d ON m.key=d.key ORDER BY m.key",
            )
        return {
            "format": (
                "nexus-osis-v1" if self.workspace_id == "osis" else "nexus-core-v1"
            ),
            "workspace": self.workspace_id,
            "schema_version": 2,
            "exported_at": now(),
            **data,
        }

    def search(self, query: str) -> dict:
        """Bounded literal substring search across workspace facts/projects/history."""
        self.require("read")
        query = clean_text(query, "Search query", 200)
        pattern = (
            "%"
            + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        with self._conn() as con:
            return {
                "facts": self._rows(
                    con,
                    "SELECT m.*, p.source, p.created_at, p.approved_at, p.approval_id,d.category,d.source_ref,d.valid_until,d.confirmation FROM memories m LEFT JOIN memory_metadata p ON m.key=p.key LEFT JOIN memory_details d ON m.key=d.key WHERE m.key LIKE ? ESCAPE '\\' OR m.value LIKE ? ESCAPE '\\' ORDER BY m.updated_at DESC LIMIT 50",
                    (pattern, pattern),
                ),
                "projects": self._rows(
                    con,
                    "SELECT * FROM projects WHERE title LIKE ? ESCAPE '\\' OR goal LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 50",
                    (pattern, pattern),
                ),
                "history": self._rows(
                    con,
                    "SELECT * FROM messages WHERE content LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 50",
                    (pattern,),
                ),
                "notes": self._rows(
                    con,
                    "SELECT * FROM notes WHERE title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT 50",
                    (pattern, pattern),
                ),
            }

    def log_event(self, event: str, detail: str):
        """Only host code calls this; error callers supply categories, not exception text."""
        self.require("propose")
        with self._conn() as con:
            con.execute(
                "INSERT INTO audit(at,event,detail) VALUES(?,?,?)",
                (now(), event, detail),
            )

    def approval_status(self, action_id: str) -> str:
        self.require("read")
        with self._conn() as con:
            row = con.execute(
                "SELECT status FROM pending_actions WHERE id=?", (action_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Action not found")
            return row["status"]

    def start_command(self, message: str, intent: str) -> str:
        self.require("propose")
        command_id = secrets.token_urlsafe(18)
        with self._conn() as con:
            con.execute(
                "INSERT INTO command_runs(id,command,intent,status,created_at,updated_at) VALUES(?,?,?,'received',?,?)",
                (command_id, message, intent, now(), now()),
            )
            con.execute(
                "INSERT INTO command_transitions(command_id,from_status,to_status,at) VALUES(?,'','received',?)",
                (command_id, now()),
            )
            transition(con, command_id, "planning")
        return command_id

    def finish_command(self, command_id: str, result: dict):
        with self._conn() as con:
            pending = result.get("pending")
            status = (
                "awaiting_approval"
                if pending
                else "failed" if result.get("status") == "error" else "completed"
            )
            transition(
                con,
                command_id,
                status,
                result={"kind": result.get("kind"), "message": result["message"]},
                error="command_failed" if status == "failed" else None,
                action_id=pending["id"] if pending else None,
            )

    def command(self, command_id: str) -> dict:
        self.require("read")
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM command_runs WHERE id=?", (command_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Command not found")
            result = dict(row)
            result["workspace"] = self.workspace_id
            result["history"] = self._rows(
                con,
                "SELECT from_status,to_status,at FROM command_transitions WHERE command_id=? ORDER BY id",
                (command_id,),
            )
            if result["result_json"]:
                result["result"] = json.loads(result.pop("result_json"))
            return result

    def plans(self, plan_id=None) -> list[dict]:
        self.require("read")
        with self._conn() as con:
            sql = "SELECT r.*,p.name,p.args_json,p.expires_at,p.status AS approval_status FROM plan_records r JOIN pending_actions p ON p.id=r.id"
            rows = self._rows(
                con,
                sql
                + (
                    " WHERE r.id=?"
                    if plan_id
                    else " ORDER BY r.created_at DESC LIMIT 50"
                ),
                (plan_id,) if plan_id else (),
            )
            for row in rows:
                row["workspace"] = self.workspace_id
                row["arguments"] = json.loads(row.pop("args_json"))
                row["result"] = (
                    json.loads(row.pop("result_json"))
                    if row.get("result_json")
                    else None
                )
            return rows
