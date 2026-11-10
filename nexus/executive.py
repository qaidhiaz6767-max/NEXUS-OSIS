"""Transactional project, milestone, task and meeting relationships."""

import json
from .validation import now


class RecordNotFound(ValueError, LookupError):
    pass


def require_record(con, table, record_id):
    if table not in {
        "tasks",
        "projects",
        "milestones",
        "meetings",
        "decisions",
        "meeting_actions",
    }:
        raise ValueError("Unsupported record type.")
    row = con.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
    if row is None:
        raise RecordNotFound(f"{table} record #{record_id} does not exist.")
    return dict(row)


def link_task(
    con,
    task_id,
    project_id=None,
    milestone_id=None,
    description="",
    follow_up_context="",
):
    if project_id is not None:
        require_record(con, "projects", project_id)
    if milestone_id is not None:
        milestone = require_record(con, "milestones", milestone_id)
        if project_id is None or milestone["project_id"] != project_id:
            raise ValueError("Milestone must belong to the selected project.")
    con.execute(
        """INSERT INTO task_details(task_id,description,project_id,milestone_id,follow_up_context) VALUES(?,?,?,?,?)
        ON CONFLICT(task_id) DO UPDATE SET description=excluded.description,project_id=excluded.project_id,
        milestone_id=excluded.milestone_id,follow_up_context=excluded.follow_up_context""",
        (task_id, description, project_id, milestone_id, follow_up_context),
    )


def add_dependency(con, task_id, depends_on):
    task = require_record(con, "tasks", task_id)
    require_record(con, "tasks", depends_on)
    if task["status"] == "done":
        raise ValueError("Reopen a completed task before adding prerequisites.")
    if task_id == depends_on:
        raise ValueError("A task cannot depend on itself.")
    graph = {}
    for row in con.execute("SELECT task_id,depends_on FROM task_dependencies"):
        graph.setdefault(row[0], []).append(row[1])
    pending = [depends_on]
    seen = set()
    while pending:
        current = pending.pop()
        if current == task_id:
            raise ValueError("Task dependencies cannot contain a cycle.")
        if current in seen:
            continue
        seen.add(current)
        pending.extend(graph.get(current, []))
    con.execute(
        "INSERT OR IGNORE INTO task_dependencies VALUES(?,?)", (task_id, depends_on)
    )


def execute(con, name, args, approval_id=""):
    at = now()
    if name == "update_project":
        require_record(con, "projects", args["project_id"])
        if (
            args["status"] == "completed"
            and con.execute(
                "SELECT 1 FROM task_details d JOIN tasks t ON t.id=d.task_id WHERE d.project_id=? AND t.status!='done' LIMIT 1",
                (args["project_id"],),
            ).fetchone()
        ):
            raise ValueError("Complete the linked tasks before completing the project.")
        con.execute(
            "UPDATE projects SET title=?,goal=?,status=? WHERE id=?",
            (args["title"], args["goal"], args["status"], args["project_id"]),
        )
        con.execute(
            "INSERT INTO project_details VALUES(?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET owner=excluded.owner,target_date=excluded.target_date,updated_at=excluded.updated_at",
            (args["project_id"], args["owner"], args["target_date"], at),
        )
        return f"Project #{args['project_id']} updated."
    if name == "create_milestone":
        require_record(con, "projects", args["project_id"])
        cur = con.execute(
            "INSERT INTO milestones(project_id,title,target_date,status,created_at,updated_at) VALUES(?,?,?,'planned',?,?)",
            (args["project_id"], args["title"], args["target_date"], at, at),
        )
        return f"Milestone #{cur.lastrowid} created."
    if name == "set_milestone_status":
        require_record(con, "milestones", args["milestone_id"])
        if (
            args["status"] == "done"
            and con.execute(
                "SELECT 1 FROM task_details d JOIN tasks t ON d.task_id=t.id WHERE milestone_id=? AND t.status!='done' LIMIT 1",
                (args["milestone_id"],),
            ).fetchone()
        ):
            raise ValueError("Complete the milestone tasks first.")
        con.execute(
            "UPDATE milestones SET status=?,updated_at=? WHERE id=?",
            (args["status"], at, args["milestone_id"]),
        )
        return f"Milestone #{args['milestone_id']} updated."
    if name == "update_task":
        require_record(con, "tasks", args["task_id"])
        link_task(
            con,
            args["task_id"],
            args["project_id"],
            args["milestone_id"],
            args["description"],
            args["follow_up_context"],
        )
        con.execute(
            "UPDATE tasks SET title=?,owner=?,due_date=?,priority=? WHERE id=?",
            (
                args["title"],
                args["owner"],
                args["due_date"],
                args["priority"],
                args["task_id"],
            ),
        )
        con.execute(
            "UPDATE conversation_references SET last_task_id=? WHERE singleton=1",
            (args["task_id"],),
        )
        return f"Task #{args['task_id']} updated. Assignment recorded locally; no notification sent."
    if name == "add_dependency":
        add_dependency(con, args["task_id"], args["depends_on"])
        return f"Task #{args['task_id']} now depends on task #{args['depends_on']}."
    if name == "create_project_plan":
        project = con.execute(
            "INSERT INTO projects(title,goal,status,created_at) VALUES(?,?,'active',?)",
            (args["title"], args["goal"], at),
        ).lastrowid
        con.execute(
            "INSERT INTO project_details VALUES(?,?,?,?)",
            (project, args["owner"], args["target_date"], at),
        )
        milestone_ids = []
        task_ids = []
        for milestone in args["milestones"]:
            milestone_ids.append(
                con.execute(
                    "INSERT INTO milestones(project_id,title,target_date,status,created_at,updated_at) VALUES(?,?,?,'planned',?,?)",
                    (project, milestone["title"], milestone["target_date"], at, at),
                ).lastrowid
            )
        for task in args["tasks"]:
            task_id = con.execute(
                "INSERT INTO tasks(title,owner,due_date,priority,status,created_at) VALUES(?,?,?,?,'todo',?)",
                (task["title"], task["owner"], task["due_date"], task["priority"], at),
            ).lastrowid
            task_ids.append(task_id)
            milestone = (
                milestone_ids[task["milestone_number"] - 1]
                if task["milestone_number"]
                else None
            )
            link_task(con, task_id, project, milestone, task["description"])
            for dependency in task["depends_on"]:
                add_dependency(con, task_id, task_ids[dependency - 1])
        con.execute(
            "UPDATE conversation_references SET last_project_id=?,last_task_id=NULL WHERE singleton=1",
            (project,),
        )
        return f"Project #{project} created with {len(milestone_ids)} milestones and tasks {', '.join('#'+str(i) for i in task_ids)}. All records committed together; notifications not sent."
    if name == "create_meeting":
        if args["project_id"] is not None:
            require_record(con, "projects", args["project_id"])
        meeting = con.execute(
            "INSERT INTO meetings(title,held_on,project_id,agenda,draft_minutes,participants_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                args["title"],
                args["held_on"],
                args["project_id"],
                args["agenda"],
                args["draft_minutes"],
                json.dumps(args["participants"]),
                at,
                at,
            ),
        ).lastrowid
        con.execute(
            "UPDATE conversation_references SET last_meeting_id=? WHERE singleton=1",
            (meeting,),
        )
        return f"Meeting #{meeting} saved. Minutes remain a draft; no decisions or attendance were inferred."
    if name == "record_decision":
        if args["meeting_id"] is not None:
            require_record(con, "meetings", args["meeting_id"])
        if args["project_id"] is not None:
            require_record(con, "projects", args["project_id"])
        if args["meeting_id"] and args["project_id"]:
            meeting = require_record(con, "meetings", args["meeting_id"])
            if meeting["project_id"] not in (None, args["project_id"]):
                raise ValueError("Meeting and decision project do not match.")
        item = con.execute(
            "INSERT INTO decisions(meeting_id,project_id,title,body,status,source_ref,created_at) VALUES(?,?,?,?,'draft',?,?)",
            (
                args["meeting_id"],
                args["project_id"],
                args["title"],
                args["body"],
                args["source_ref"],
                at,
            ),
        ).lastrowid
        return f"Decision draft #{item} saved. It is not an approved decision yet."
    if name == "approve_decision":
        row = require_record(con, "decisions", args["decision_id"])
        if row["status"] != "draft":
            raise ValueError("Decision was already approved.")
        con.execute(
            "UPDATE decisions SET status='approved',approved_at=?,approval_id=? WHERE id=?",
            (at, approval_id, args["decision_id"]),
        )
        return f"Decision #{args['decision_id']} approved by the local operator."
    if name == "record_meeting_action":
        require_record(con, "meetings", args["meeting_id"])
        item = con.execute(
            "INSERT INTO meeting_actions(meeting_id,title,owner,due_date,priority,status,created_at) VALUES(?,?,?,?,?,'draft',?)",
            (
                args["meeting_id"],
                args["title"],
                args["owner"],
                args["due_date"],
                args["priority"],
                at,
            ),
        ).lastrowid
        return f"Meeting action draft #{item} saved. Confirm it before creating a task."
    if name == "confirm_meeting_action":
        row = require_record(con, "meeting_actions", args["action_item_id"])
        if row["status"] != "draft":
            raise ValueError("Meeting action is already confirmed.")
        con.execute(
            "UPDATE meeting_actions SET status='confirmed' WHERE id=?", (row["id"],)
        )
        return f"Meeting action #{row['id']} confirmed."
    if name == "create_followup_task":
        row = require_record(con, "meeting_actions", args["action_item_id"])
        if row["status"] != "confirmed" or row["task_id"] is not None:
            raise ValueError(
                "Follow-up must be confirmed and must not already have a task."
            )
        meeting = require_record(con, "meetings", row["meeting_id"])
        task = con.execute(
            "INSERT INTO tasks(title,owner,due_date,priority,status,created_at) VALUES(?,?,?,?,'todo',?)",
            (row["title"], row["owner"], row["due_date"], row["priority"], at),
        ).lastrowid
        link_task(
            con,
            task,
            meeting["project_id"],
            description="Confirmed follow-up from meeting #" + str(meeting["id"]),
        )
        con.execute(
            "UPDATE meeting_actions SET task_id=? WHERE id=?", (task, row["id"])
        )
        con.execute(
            "UPDATE conversation_references SET last_task_id=? WHERE singleton=1",
            (task,),
        )
        return f"Task #{task} created from confirmed meeting action #{row['id']}. No notification sent."
    raise ValueError("Unsupported executive action.")
