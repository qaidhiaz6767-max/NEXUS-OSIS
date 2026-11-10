"""Grounded executive reports over real workspace records."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from .validation import today_local, configured_timezone


def build_briefing(store, period="today", owner=""):
    store.require("read")
    if period not in {"today", "week", "unfinished"}:
        raise ValueError("Unsupported reporting period.")
    today = today_local()
    end = today + timedelta(days=7)
    with store._conn() as con:
        con.execute("BEGIN")
        tasks = store._rows(
            con,
            "SELECT t.*,d.project_id,d.completed_at FROM tasks t LEFT JOIN task_details d ON d.task_id=t.id WHERE (?='' OR t.owner=? COLLATE NOCASE) ORDER BY t.id",
            (owner, owner),
        )
        events = store._rows(
            con,
            "SELECT * FROM events WHERE day>=? AND day<=? ORDER BY day,time,id",
            (today.isoformat(), end.isoformat()),
        )
        projects = store._rows(
            con,
            "SELECT p.*,d.target_date,d.owner FROM projects p LEFT JOIN project_details d ON p.id=d.project_id ORDER BY p.id",
        )
        dependencies = store._rows(
            con,
            "SELECT d.task_id,d.depends_on FROM task_dependencies d JOIN tasks t ON d.depends_on=t.id WHERE t.status!='done'",
        )
        decisions = store._rows(
            con,
            "SELECT id,title,approved_at,meeting_id,project_id FROM decisions WHERE status='approved' ORDER BY id DESC LIMIT 10",
        )
        pending = con.execute(
            "SELECT count(*) FROM pending_actions WHERE status='pending' AND expires_at>?",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"),),
        ).fetchone()[0]
    open_tasks = [task for task in tasks if task["status"] != "done"]
    priorities = sorted(
        open_tasks,
        key=lambda task: (
            not bool(task["due_date"] and task["due_date"] < today.isoformat()),
            {"high": 0, "medium": 1, "low": 2}.get(task["priority"], 3),
            task["due_date"] or "9999",
            task["id"],
        ),
    )
    overdue = [
        task
        for task in open_tasks
        if task["due_date"] and task["due_date"] < today.isoformat()
    ]
    due = [
        task
        for task in open_tasks
        if task["due_date"] and today.isoformat() <= task["due_date"] <= end.isoformat()
    ]
    risks = [
        project
        for project in projects
        if project["status"] not in {"completed", "archived"}
        and project["target_date"]
        and project["target_date"] < today.isoformat()
    ]

    def completed_in_period(task):
        if task["status"] != "done" or not task["completed_at"]:
            return False
        try:
            stamp = datetime.fromisoformat(task["completed_at"])
            if stamp.tzinfo is None:
                return False
            day = stamp.astimezone(ZoneInfo(configured_timezone())).date()
            return today - timedelta(days=6) <= day <= today
        except (ValueError, TypeError):
            return False

    completed = [task for task in tasks if completed_in_period(task)]
    open_ids = {task["id"] for task in open_tasks}
    dependencies = [item for item in dependencies if item["task_id"] in open_ids]
    unknown_completion = sum(
        task["status"] == "done" and not task["completed_at"] for task in tasks
    )
    report = {
        "workspace": store.workspace_id,
        "period": {
            "kind": period,
            "from": today.isoformat(),
            "to": end.isoformat(),
            "timezone": configured_timezone(),
        },
        "completion_period": {
            "from": (today - timedelta(days=6)).isoformat(),
            "to": today.isoformat(),
        },
        "task_filter": {"owner": owner or None},
        "sources": {
            "tasks": [task["id"] for task in tasks],
            "projects": [project["id"] for project in projects],
            "events": [event["id"] for event in events],
            "approved_decisions": [item["id"] for item in decisions],
        },
        "counts": {
            "open_tasks": len(open_tasks),
            "overdue": len(overdue),
            "due_soon": len(due),
            "pending_approvals": pending,
            "active_projects": sum(p["status"] == "active" for p in projects),
        },
        "priorities": priorities[:10],
        "upcoming_events": events[:10],
        "project_risks": risks[:10],
        "blockers": dependencies[:30],
        "completed_last_7_days": completed[:30],
        "completion_time_unknown": unknown_completion,
        "approved_decisions": decisions,
        "recommendations": [],
        "authority_level": 0,
    }
    if priorities:
        report["recommendations"].append(
            f"Review task #{priorities[0]['id']} first, using overdue/priority/deadline ordering. No assignment has been changed."
        )
    if pending:
        report["recommendations"].append(
            f"Review the {pending} pending approvals before treating proposed work as completed."
        )
    lines = [
        f"{store.workspace_id.upper()} BRIEFING — {today.isoformat()}",
        f"Open tasks: {len(open_tasks)} | Overdue: {len(overdue)} | Due within 7 days: {len(due)}",
        f"Reporting period: {today.isoformat()} to {end.isoformat()} ({configured_timezone()})",
        f'Active projects: {report["counts"]["active_projects"]} | Pending approvals: {pending}',
    ]
    if priorities:
        lines += ["", "PRIORITIES:"] + [
            f"• #{t['id']} {t['title']} — {t['owner']} — {t['due_date'] or 'deadline not set'}"
            for t in priorities[:8]
        ]
    if events:
        lines += ["", "NEXT EVENTS:"] + [
            f"• #{e['id']} {e['day']} {e['time'] or 'time not set'} — {e['title']}"
            for e in events[:5]
        ]
    if risks:
        lines += ["", "PROJECTS PAST TARGET:"] + [
            f"• Project #{p['id']} {p['title']} — target {p['target_date']}"
            for p in risks[:5]
        ]
    if period == "week":
        lines += [
            "",
            f"Completed in last 7 days with recorded timestamps: {len(completed)}. Historical completion time unknown: {unknown_completion}.",
        ]
    if report["recommendations"]:
        lines += [
            "",
            "RECOMMENDATIONS (deterministic, not completed actions):",
        ] + report["recommendations"]
    if not priorities and not events:
        lines.append("No active tasks or upcoming events in the reporting window.")
    lines += [
        "",
        f"Sources: {len(tasks)} task records, {len(projects)} project records, {len(events)} event records; only approved decisions are included.",
    ]
    report["message"] = "\n".join(lines)
    return report
