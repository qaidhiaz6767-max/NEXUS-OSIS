"""Bounded read-only tools, always bound to the coordinator's workspace Store."""

from .validation import clean_text, pos_int, iso_day, today_local
from .briefing import build_briefing
from .executive import require_record
from .tools import tool

READ_TOOLS = [
    tool(
        "read_tasks",
        "Retrieve stored local tasks, not proposed or notified assignments",
        {"status": "string", "owner": "string"},
    ),
    tool(
        "search_memory",
        "Search confirmed facts, notes, projects and history in this workspace",
        {"query": "string"},
    ),
    tool(
        "get_project",
        "Retrieve a project and its actual relationships",
        {"project_id": "integer"},
    ),
    tool(
        "review_events",
        "Read existing local events",
        {"from_day": "string", "to_day": "string"},
    ),
    tool(
        "generate_briefing",
        "Generate a grounded workspace briefing",
        {"period": "string", "owner": "string"},
    ),
]
READ_NAMES = frozenset(item["name"] for item in READ_TOOLS)


def read_tool(store, name, args):
    store.require("read")
    if not isinstance(args, dict):
        raise ValueError("Read tool arguments must be an object.")
    allowed = {
        item["name"]: set(item["parameters"]["properties"]) for item in READ_TOOLS
    }
    if name not in allowed or set(args) - allowed[name]:
        raise ValueError("Unsupported read tool or argument.")
    if name == "read_tasks":
        status = clean_text(args.get("status", "all"), "Status", 10)
        if status not in {"all", "todo", "doing", "done"}:
            raise ValueError("Invalid task status.")
        owner = clean_text(args.get("owner", ""), "Owner", 100, False)
        with store._conn() as con:
            return store._rows(
                con,
                "SELECT * FROM tasks WHERE (?='all' OR status=?) AND (?='' OR owner=? COLLATE NOCASE) ORDER BY id DESC LIMIT 50",
                (status, status, owner, owner),
            )
    if name == "search_memory":
        return store.search(clean_text(args.get("query", ""), "Query", 200))
    if name == "generate_briefing":
        return build_briefing(
            store,
            args.get("period", "today"),
            clean_text(args.get("owner", ""), "Owner", 100, False),
        )
    if name == "review_events":
        start = iso_day(args.get("from_day", "")) or today_local().isoformat()
        end = iso_day(args.get("to_day", "")) or start
        if end < start:
            raise ValueError("End date precedes start date.")
        with store._conn() as con:
            return store._rows(
                con,
                "SELECT * FROM events WHERE day>=? AND day<=? ORDER BY day,time LIMIT 50",
                (start, end),
            )
    if name == "get_project":
        project_id = pos_int(args.get("project_id"))
        with store._conn() as con:
            project = require_record(con, "projects", project_id)
            details = con.execute(
                "SELECT * FROM project_details WHERE project_id=?", (project_id,)
            ).fetchone()
            if details:
                project.update(dict(details))
            return {
                "project": project,
                "milestones": store._rows(
                    con,
                    "SELECT * FROM milestones WHERE project_id=? ORDER BY id",
                    (project_id,),
                ),
                "tasks": store._rows(
                    con,
                    "SELECT t.*,d.description,d.completed_at FROM task_details d JOIN tasks t ON t.id=d.task_id WHERE d.project_id=? ORDER BY t.id LIMIT 100",
                    (project_id,),
                ),
                "meetings": store._rows(
                    con,
                    "SELECT * FROM meetings WHERE project_id=? ORDER BY id DESC LIMIT 30",
                    (project_id,),
                ),
                "decisions": store._rows(
                    con,
                    "SELECT * FROM decisions WHERE project_id=? AND status='approved' ORDER BY id DESC LIMIT 30",
                    (project_id,),
                ),
            }
    raise ValueError("Unsupported read tool.")
