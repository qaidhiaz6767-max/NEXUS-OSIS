"""Allowlisted action schemas and bounded input validation."""
from __future__ import annotations
import json
import os
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ACTIONS = frozenset({"create_task", "set_task_status", "assign_task", "create_event", "create_note", "remember", "create_project", "forget", "execute_plan"})
STATUSES = frozenset({"todo", "doing", "done"})
PRIORITIES = frozenset({"low", "medium", "high"})


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_local() -> date:
    """Use the OSIS operating timezone for briefings, independent of CI/server TZ."""
    try:
        return datetime.now(ZoneInfo(os.getenv("NEXUS_TIMEZONE", "Asia/Jakarta"))).date()
    except ZoneInfoNotFoundError:
        # If a platform lacks zoneinfo data, retain functional offline commands.
        return date.today()


def clean_text(value, label: str, max_length: int = 240, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{label} cannot be empty.")
    if len(value) > max_length:
        raise ValueError(f"{label} must be at most {max_length} characters.")
    if "\x00" in value:
        raise ValueError(f"{label} cannot contain null bytes.")
    return value


def iso_day(value: str, required: bool = False) -> str:
    value = clean_text(value, "Date", 10, required=required)
    if value:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Date must be a real date in YYYY-MM-DD format.") from exc
        if parsed.isoformat() != value:
            raise ValueError("Date must be YYYY-MM-DD.")
    return value


def iso_time(value: str) -> str:
    value = clean_text(value, "Time", 5, required=False)
    if value and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Time must be HH:MM (24-hour clock).")
    return value


def pos_int(value, label: str = "ID") -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer.")
    try:
        result = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be a positive integer.") from exc
    if result < 1 or str(value).strip() != str(result):
        raise ValueError(f"{label} must be a positive integer.")
    return result


def validate_action(name: str, args: dict) -> dict:
    if not isinstance(name, str) or name not in ACTIONS or not isinstance(args, dict):
        raise ValueError("Unsupported action.")
    if name == "execute_plan":
        steps = args.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 5:
            raise ValueError("A plan requires 1 to 5 steps")
        normalized = []
        for step in steps:
            if not isinstance(step, dict) or step.get("name") == "execute_plan":
                raise ValueError("Nested or invalid plan step")
            step_args = step.get("args")
            if step_args is None and isinstance(step.get("arguments_json"), str):
                try:
                    step_args = json.loads(step["arguments_json"])
                except json.JSONDecodeError as exc:
                    raise ValueError("Invalid step arguments JSON") from exc
            normalized.append({"name": step.get("name"),
                               "args": validate_action(step.get("name"), step_args)})
        return {"steps": normalized}
    if name == "forget":
        return {"key": clean_text(args.get("key", ""), "Memory key", 100)}
    if name == "create_project":
        return {"title": clean_text(args.get("title", ""), "Project title"),
                "goal": clean_text(args.get("goal", ""), "Project goal", 2000),
                "status": "active"}
    # Model-supplied extra keys are ignored, never interpreted.
    if name == "create_task":
        priority = clean_text(args.get("priority", "medium"), "Priority", 10).lower()
        if priority not in PRIORITIES:
            raise ValueError("Priority must be low, medium, or high.")
        return {
            "title": clean_text(args.get("title", ""), "Task title"),
            "owner": clean_text(args.get("owner", "Unassigned"), "Owner", 100),
            "due_date": iso_day(args.get("due_date", "")),
            "priority": priority,
        }
    if name == "set_task_status":
        status = clean_text(args.get("status", ""), "Status", 10).lower()
        if status not in STATUSES:
            raise ValueError("Status must be todo, doing, or done.")
        return {"task_id": pos_int(args.get("task_id"), "Task ID"), "status": status}
    if name == "assign_task":
        return {"task_id": pos_int(args.get("task_id"), "Task ID"),
                "owner": clean_text(args.get("owner", ""), "Owner", 100)}
    if name == "create_event":
        return {"title": clean_text(args.get("title", ""), "Event title"),
                "day": iso_day(args.get("day", ""), required=True),
                "time": iso_time(args.get("time", "")),
                "location": clean_text(args.get("location", ""), "Location", 180, required=False),
                "details": clean_text(args.get("details", ""), "Details", 1500, required=False)}
    if name == "create_note":
        return {"title": clean_text(args.get("title", ""), "Note title"),
                "body": clean_text(args.get("body", ""), "Note body", 5000)}
    return {"key": clean_text(args.get("key", ""), "Memory key", 100),
            "value": clean_text(args.get("value", ""), "Memory value", 2000)}


def action_description(name: str, args: dict) -> str:
    if name == "execute_plan":
        return "Review entire plan (all steps run together):\n" + "\n".join(
            f"{i}. {action_description(step['name'], step['args'])}"
            for i, step in enumerate(args["steps"], 1))
    if name == "forget":
        return f"Delete saved memory: {args['key']}"
    if name == "create_project":
        return f"Create project: {args['title']} — {args['goal']}"
    if name == "create_task":
        return f"Create task: {args['title']} (owner: {args['owner']}, due: {args['due_date'] or 'not set'})"
    if name == "set_task_status":
        return f"Set task #{args['task_id']} status to {args['status']}"
    if name == "assign_task":
        return f"Assign task #{args['task_id']} to {args['owner']}"
    if name == "create_event":
        return f"Schedule event: {args['title']} on {args['day']} at {args['time'] or 'time TBD'}"
    if name == "create_note":
        return f"Save note: {args['title']}"
    return f"Remember: {args['key']} = {args['value'][:120]}"
