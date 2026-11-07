"""Persistent plan/command state and optimistic approval snapshots."""

import hashlib
import json
from .validation import now

STATES = frozenset(
    {
        "received",
        "planning",
        "awaiting_approval",
        "executing",
        "completed",
        "failed",
        "cancelled",
    }
)


def transition(con, command_id, status, *, result=None, error=None, action_id=None):
    if status not in STATES:
        raise ValueError("Invalid command state.")
    row = con.execute(
        "SELECT status FROM command_runs WHERE id=?", (command_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Command not found.")
    previous = row["status"]
    allowed = {
        "received": {"planning", "failed", "cancelled"},
        "planning": {"awaiting_approval", "completed", "failed", "cancelled"},
        "awaiting_approval": {"executing", "failed", "cancelled"},
        "executing": {"completed", "failed", "cancelled"},
        "failed": {"executing", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }
    if previous != status and status not in allowed[previous]:
        raise ValueError("Invalid command state transition.")
    at = now()
    con.execute(
        "UPDATE command_runs SET status=?,updated_at=?,result_json=?,error_code=?,action_id=coalesce(?,action_id) WHERE id=?",
        (
            status,
            at,
            json.dumps(result, ensure_ascii=False) if result is not None else None,
            error,
            action_id,
            command_id,
        ),
    )
    if previous != status:
        con.execute(
            "INSERT INTO command_transitions(command_id,from_status,to_status,at) VALUES(?,?,?,?)",
            (command_id, previous, status, at),
        )


def plan_transition(con, action_id, status, *, result=None, error=None):
    con.execute(
        "UPDATE plan_records SET status=?,updated_at=?,result_json=?,error_code=? WHERE id=?",
        (
            status,
            now(),
            json.dumps(result, ensure_ascii=False) if result is not None else None,
            error,
            action_id,
        ),
    )
    for row in con.execute(
        "SELECT id,status FROM command_runs WHERE action_id=?", (action_id,)
    ).fetchall():
        if row["status"] not in {"completed", "cancelled"}:
            transition(con, row["id"], status, result=result, error=error)


def _snapshot(con, table, key):
    if table not in {
        "tasks",
        "projects",
        "milestones",
        "meetings",
        "decisions",
        "meeting_actions",
        "memories",
    }:
        raise ValueError("Unsupported snapshot type.")
    column = "key" if table == "memories" else "id"
    row = con.execute(f"SELECT * FROM {table} WHERE {column}=?", (key,)).fetchone()
    data = dict(row) if row else None
    sidecars = {
        "tasks": ("task_details", "task_id"),
        "projects": ("project_details", "project_id"),
        "memories": ("memory_details", "key"),
    }
    if table in sidecars:
        side, column = sidecars[table]
        extra = con.execute(f"SELECT * FROM {side} WHERE {column}=?", (key,)).fetchone()
        data = {"record": data, "details": dict(extra) if extra else None}
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def fingerprints(con, name, args):
    if name == "execute_plan":
        merged = {}
        for step in args["steps"]:
            merged.update(fingerprints(con, step["name"], step["args"]))
        return merged
    records = []
    if name in {"remember", "forget"}:
        records.append(("memories", args["key"]))
    for key, table in [
        ("task_id", "tasks"),
        ("depends_on", "tasks"),
        ("project_id", "projects"),
        ("milestone_id", "milestones"),
        ("meeting_id", "meetings"),
        ("decision_id", "decisions"),
        ("action_item_id", "meeting_actions"),
    ]:
        value = args.get(key)
        if value is not None:
            records.append((table, value))
    return {
        json.dumps([table, key]): _snapshot(con, table, key) for table, key in records
    }


def verify_fingerprints(con, action_id):
    row = con.execute(
        "SELECT fingerprints_json FROM pending_context WHERE action_id=?", (action_id,)
    ).fetchone()
    if not row:
        return  # Legacy proposals remain compatible.
    for identifier, expected in json.loads(row[0]).items():
        table, key = json.loads(identifier)
        if _snapshot(con, table, key) != expected:
            raise ValueError(
                "A referenced record changed since this proposal. Request a new proposal before approving."
            )
