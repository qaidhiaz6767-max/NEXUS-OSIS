"""Explicit schemas for executive records; no executable code in plan steps."""

EXECUTIVE_ACTIONS = frozenset(
    {
        "update_project",
        "create_milestone",
        "set_milestone_status",
        "update_task",
        "add_dependency",
        "create_project_plan",
        "create_meeting",
        "record_decision",
        "approve_decision",
        "record_meeting_action",
        "confirm_meeting_action",
        "create_followup_task",
    }
)
PROJECT_STATUSES = frozenset({"planned", "active", "on_hold", "completed", "archived"})


def validate_executive(name, args):
    from .validation import clean_text, iso_day, pos_int, PRIORITIES

    def text(key, label=None, limit=240, required=True, default=""):
        return clean_text(args.get(key, default), label or key, limit, required)

    def optional_id(key):
        return None if args.get(key) in (None, "") else pos_int(args[key], key)

    def priority():
        value = text("priority", limit=10, default="medium").lower()
        if value not in PRIORITIES:
            raise ValueError("Invalid priority.")
        return value

    if name == "update_project":
        status = text("status", limit=16, default="active")
        if status not in PROJECT_STATUSES:
            raise ValueError("Invalid project status.")
        return {
            "project_id": pos_int(args.get("project_id")),
            "title": text("title"),
            "goal": text("goal", limit=2000),
            "owner": text("owner", limit=100, default="Unassigned"),
            "target_date": iso_day(args.get("target_date", "")),
            "status": status,
        }
    if name == "create_milestone":
        return {
            "project_id": pos_int(args.get("project_id")),
            "title": text("title"),
            "target_date": iso_day(args.get("target_date", "")),
        }
    if name == "set_milestone_status":
        status = text("status", limit=10)
        if status not in {"planned", "done"}:
            raise ValueError("Invalid milestone status.")
        return {"milestone_id": pos_int(args.get("milestone_id")), "status": status}
    if name == "update_task":
        return {
            "task_id": pos_int(args.get("task_id")),
            "title": text("title"),
            "owner": text("owner", limit=100, default="Unassigned"),
            "due_date": iso_day(args.get("due_date", "")),
            "priority": priority(),
            "description": text("description", limit=2000, required=False),
            "project_id": optional_id("project_id"),
            "milestone_id": optional_id("milestone_id"),
            "follow_up_context": text("follow_up_context", limit=2000, required=False),
        }
    if name == "add_dependency":
        return {
            "task_id": pos_int(args.get("task_id")),
            "depends_on": pos_int(args.get("depends_on")),
        }
    if name == "create_project_plan":
        milestones = args.get("milestones", [])
        tasks = args.get("tasks", [])
        if not isinstance(milestones, list) or len(milestones) > 5:
            raise ValueError("Use at most five milestones.")
        if not isinstance(tasks, list) or not 1 <= len(tasks) <= 20:
            raise ValueError("Use 1 to 20 planned tasks.")
        normalized_milestones = []
        normalized_tasks = []
        for item in milestones:
            if not isinstance(item, dict):
                raise ValueError("Invalid milestone.")
            normalized_milestones.append(
                {
                    "title": clean_text(item.get("title", ""), "Milestone title"),
                    "target_date": iso_day(item.get("target_date", "")),
                }
            )
        for number, item in enumerate(tasks, 1):
            if not isinstance(item, dict):
                raise ValueError("Invalid planned task.")
            p = clean_text(item.get("priority", "medium"), "Priority", 10)
            if p not in PRIORITIES:
                raise ValueError("Invalid task priority.")
            dependencies = item.get("depends_on", [])
            if not isinstance(dependencies, list):
                raise ValueError("Dependencies must be step numbers.")
            dependencies = [pos_int(value, "Dependency step") for value in dependencies]
            if len(set(dependencies)) != len(dependencies) or any(
                value >= number for value in dependencies
            ):
                raise ValueError(
                    "Dependencies must refer to distinct earlier task numbers."
                )
            milestone = item.get("milestone_number")
            if milestone is not None:
                milestone = pos_int(milestone, "Milestone number")
                if milestone > len(milestones):
                    raise ValueError("Unknown milestone number.")
            normalized_tasks.append(
                {
                    "title": clean_text(item.get("title", ""), "Task title"),
                    "description": clean_text(
                        item.get("description", ""), "Description", 500, False
                    ),
                    "owner": clean_text(item.get("owner", "Unassigned"), "Owner", 100),
                    "due_date": iso_day(item.get("due_date", "")),
                    "priority": p,
                    "depends_on": dependencies,
                    "milestone_number": milestone,
                }
            )
        import json

        if len({json.dumps(task, sort_keys=True) for task in normalized_tasks}) != len(
            normalized_tasks
        ):
            raise ValueError(
                "Duplicate planned tasks require distinct details or phases."
            )
        return {
            "title": text("title"),
            "goal": text("goal", limit=2000),
            "owner": text("owner", limit=100, default="Unassigned"),
            "target_date": iso_day(args.get("target_date", "")),
            "milestones": normalized_milestones,
            "tasks": normalized_tasks,
        }
    if name == "create_meeting":
        participants = args.get("participants", [])
        if not isinstance(participants, list) or len(participants) > 30:
            raise ValueError("Use at most 30 participant labels.")
        return {
            "title": text("title"),
            "held_on": iso_day(args.get("held_on", "")),
            "project_id": optional_id("project_id"),
            "agenda": text("agenda", limit=3000, required=False),
            "draft_minutes": text("draft_minutes", limit=5000, required=False),
            "participants": [
                clean_text(value, "Participant label", 100) for value in participants
            ],
        }
    if name == "record_decision":
        return {
            "meeting_id": optional_id("meeting_id"),
            "project_id": optional_id("project_id"),
            "title": text("title"),
            "body": text("body", limit=3000),
            "source_ref": text("source_ref", limit=240, required=False),
        }
    if name in {"approve_decision", "confirm_meeting_action", "create_followup_task"}:
        key = "decision_id" if name == "approve_decision" else "action_item_id"
        return {key: pos_int(args.get(key), key)}
    if name == "record_meeting_action":
        return {
            "meeting_id": pos_int(args.get("meeting_id")),
            "title": text("title"),
            "owner": text("owner", limit=100, default="Unassigned"),
            "due_date": iso_day(args.get("due_date", "")),
            "priority": priority(),
        }
    raise ValueError("Unsupported executive action.")
