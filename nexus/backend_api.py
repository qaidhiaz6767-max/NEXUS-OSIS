"""Additive, workspace-bound data API for independent frontends."""

import json
import importlib.util
from .validation import pos_int, clean_text
from .retrieval import read_tool, READ_TOOLS
from .tools import TOOLS
from .memory import relevant_context
from .briefing import build_briefing
from .executive import require_record


def get_data(store, route, query):
    store.require("read")

    def parameter(name, default=""):
        return query.get(name, [default])[0]

    if route == "/api/capabilities":
        return {
            "workspace": store.workspace_id,
            "authority": {
                "supported": [0, 1, 2, 3],
                "scheduled_enabled": False,
                "specialist_agents_enabled": False,
            },
            "read_tools": READ_TOOLS,
            "proposal_tools": TOOLS,
            "external_accounts_connected": False,
            "voice": {
                "backend_audio_ingest": False,
                "browser_transcript_submission": "/api/chat",
            },
            "backup": {
                "encrypted_cli": True,
                "dependency_available": importlib.util.find_spec("cryptography")
                is not None,
                "http_restore": False,
            },
            "features": {
                "project_relationships": True,
                "milestones": True,
                "meeting_decisions": True,
                "persistent_plans": True,
                "read_only_tools": True,
            },
        }
    if route == "/api/briefing":
        return build_briefing(
            store,
            parameter("period", "today"),
            clean_text(parameter("owner"), "Owner", 100, False),
        )
    if route == "/api/context":
        return relevant_context(store, clean_text(parameter("q"), "Query", 200))
    if route == "/api/plans":
        return {"workspace": store.workspace_id, "plans": store.plans()}
    if route.startswith("/api/plans/"):
        plans = store.plans(
            clean_text(route.removeprefix("/api/plans/"), "Plan ID", 128)
        )
        if not plans:
            raise LookupError("Plan not found")
        return plans[0]
    if route.startswith("/api/commands/"):
        command_id = clean_text(route.removeprefix("/api/commands/"), "Command ID", 128)
        try:
            return store.command(command_id)
        except ValueError as exc:
            raise LookupError("Command not found") from exc
    if route == "/api/projects":
        return {"workspace": store.workspace_id, "projects": store.state()["projects"]}
    if route.startswith("/api/projects/"):
        result = read_tool(
            store,
            "get_project",
            {"project_id": pos_int(route.removeprefix("/api/projects/"))},
        )
        result["workspace"] = store.workspace_id
        return result
    if route == "/api/tasks":
        return {"workspace": store.workspace_id, "tasks": store.state()["tasks"]}
    if route.startswith("/api/tasks/"):
        task_id = pos_int(route.removeprefix("/api/tasks/"))
        with store._conn() as con:
            task = require_record(con, "tasks", task_id)
            extra = con.execute(
                "SELECT * FROM task_details WHERE task_id=?", (task_id,)
            ).fetchone()
            if extra:
                task.update(dict(extra))
            dependencies = store._rows(
                con,
                "SELECT t.id,t.title,t.status FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on WHERE d.task_id=? ORDER BY t.id",
                (task_id,),
            )
            return {
                "workspace": store.workspace_id,
                "task": task,
                "dependencies": dependencies,
                "blocked": any(t["status"] != "done" for t in dependencies),
                "assignment": "recorded",
                "notification": "not_sent",
                "acknowledgment": "not_tracked",
            }
    if route == "/api/meetings":
        with store._conn() as con:
            return {
                "workspace": store.workspace_id,
                "meetings": store._rows(
                    con,
                    "SELECT * FROM meetings ORDER BY held_on DESC,id DESC LIMIT 100",
                ),
            }
    if route.startswith("/api/meetings/"):
        meeting_id = pos_int(route.removeprefix("/api/meetings/"))
        with store._conn() as con:
            meeting = require_record(con, "meetings", meeting_id)
            meeting["participant_labels"] = json.loads(meeting.pop("participants_json"))
            return {
                "workspace": store.workspace_id,
                "meeting": meeting,
                "decisions": store._rows(
                    con,
                    "SELECT * FROM decisions WHERE meeting_id=? ORDER BY id",
                    (meeting_id,),
                ),
                "action_items": store._rows(
                    con,
                    "SELECT * FROM meeting_actions WHERE meeting_id=? ORDER BY id",
                    (meeting_id,),
                ),
                "minutes_status": "draft",
                "attendance_verified": False,
            }
    if route == "/api/decisions":
        status = parameter("status", "approved")
        if status not in {"draft", "approved", "all"}:
            raise ValueError("Invalid decision filter.")
        with store._conn() as con:
            return {
                "workspace": store.workspace_id,
                "decisions": store._rows(
                    con,
                    "SELECT * FROM decisions WHERE (?='all' OR status=?) ORDER BY id DESC LIMIT 100",
                    (status, status),
                ),
            }
    if route == "/api/memory":
        category = parameter("category")
        if category and category not in {
            "preference",
            "workspace",
            "project_objective",
            "decision",
            "meeting_outcome",
            "operational_fact",
        }:
            raise ValueError("Invalid memory category.")
        facts = store.state()["memories"]
        if category:
            facts = [fact for fact in facts if fact["category"] == category]
        return {
            "workspace": store.workspace_id,
            "facts": facts,
            "confirmation_meaning": "Approved to save; not independently verified truth.",
        }
    return None
