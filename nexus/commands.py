"""Deterministic local command planner."""
import re
import json
from .storage import Store
from .validation import validate_action, action_description

def split_fields(payload: str, count: int) -> list[str]:
    chunks = [x.strip() for x in payload.split("|")]
    if len(chunks) > count:
        raise ValueError(f"Too many fields; expected at most {count} separated by |.")
    return chunks + [""] * (count - len(chunks))


def offline_command(store: Store, text: str) -> dict | None:
    """Returns None for requests that require an optional AI model."""
    raw = text.strip()
    body = raw[1:].strip() if raw.startswith("/") else raw
    lower = body.lower()
    if lower.startswith("plan\n"):
        lines = [line.strip() for line in body[5:].splitlines() if line.strip()]
        if not 1 <= len(lines) <= 5:
            raise ValueError("A plan requires 1 to 5 command lines")
        collector = ProposalCollector()
        for line in lines:
            if line.lstrip("/").lower().startswith("plan"):
                raise ValueError("Nested plans are unsupported")
            result = offline_command(collector, line)
            if not result or not result.get("pending"):
                raise ValueError("Each plan line must be a supported write command")
        item = store.propose("execute_plan", {"steps": collector.steps})
        return {"message": "Review every step. This plan runs atomically only after approval.", "pending": item}
    if lower in {"help", "commands", "?"}:
        return {"message": HELP}
    if lower in {"brief", "briefing", "good morning", "morning briefing"}:
        return {"message": store.brief()}
    if lower in {"tasks", "list tasks"}:
        rows = store.state()["tasks"]
        return {"message": "TASKS\n" + ("\n".join(f"#{r['id']} [{r['status']}] {r['title']} · {r['owner']} · {r['due_date'] or 'no due date'}" for r in rows[:25]) or "No tasks yet.")}
    if lower in {"events", "calendar", "list events"}:
        rows = store.state()["events"]
        return {"message": "EVENTS\n" + ("\n".join(f"#{r['id']} {r['day']} {r['time']} — {r['title']}" for r in rows[:25]) or "No events yet.")}
    if lower in {"notes", "list notes"}:
        rows = store.state()["notes"]
        return {"message": "NOTES\n" + ("\n".join(f"#{r['id']} {r['title']}: {r['body'][:130]}" for r in rows[:15]) or "No notes yet.")}
    if lower in {"memory", "memories"}:
        rows = store.state()["memories"]
        return {"message": "MEMORY\n" + ("\n".join(f"{r['key']}: {r['value']}" for r in rows[:30]) or "No saved memories yet.")}
    if lower == "audit":
        rows = store.state()["audit"]
        return {"message": "RECENT AUDIT\n" + ("\n".join(f"{r['at']}: {r['event']} — {r['detail']}" for r in rows[:15]) or "No actions yet.")}

    if lower.startswith("search "):
        return {"message": json.dumps(store.search(body[7:]), ensure_ascii=False)[:6000]}
    if lower in {"projects", "list projects"}:
        rows = store.state()["projects"]
        return {"message": "PROJECTS\n" + ("\n".join(f"#{r['id']} {r['title']}: {r['goal']}" for r in rows) or "No projects yet.")}

    name, args = None, None
    if lower.startswith("project add "):
        title, goal = split_fields(body[12:], 2)
        name, args = "create_project", {"title": title, "goal": goal}
    elif lower.startswith("task add "):
        title, owner, due, priority = split_fields(body[9:], 4)
        name, args = "create_task", {"title": title, "owner": owner or "Unassigned", "due_date": due, "priority": priority or "medium"}
    elif lower.startswith("task done ") or lower.startswith("task doing ") or lower.startswith("task todo "):
        match = re.fullmatch(r"task (done|doing|todo)\s+(\d+)", lower)
        if not match:
            raise ValueError("Usage: /task done 1")
        name, args = "set_task_status", {"task_id": match.group(2), "status": match.group(1)}
    elif lower.startswith("task assign "):
        task_id, owner = split_fields(body[12:], 2)
        name, args = "assign_task", {"task_id": task_id, "owner": owner}
    elif lower.startswith("event add "):
        title, day, time, location, details = split_fields(body[10:], 5)
        name, args = "create_event", {"title": title, "day": day, "time": time, "location": location, "details": details}
    elif lower.startswith("note add "):
        title, content = split_fields(body[9:], 2)
        name, args = "create_note", {"title": title, "body": content}
    elif lower.startswith("forget "):
        name, args = "forget", {"key": body[7:]}
    elif lower.startswith("remember "):
        key, value = split_fields(body[9:], 2)
        name, args = "remember", {"key": key, "value": value}
    elif raw.startswith("/"):
        return {"message": "Unknown command. Type /help for available commands."}
    if name:
        item = store.propose(name, args)
        return {"message": "Please review this change. It will NOT happen until you approve it.", "pending": item}
    return None


class ProposalCollector:
    """Parse plan steps without persistence or access to other tools/data."""
    def __init__(self):
        self.steps = []

    def propose(self, name, args):
        norm = validate_action(name, args)
        self.steps.append({"name": name, "args": norm})
        return {"name": name, "args": norm}

    def state(self):
        raise ValueError("Plans accept write commands only")

    def brief(self):
        raise ValueError("Plans accept write commands only")

    def search(self, query):
        raise ValueError("Plans accept write commands only")


HELP = """NEXUS — COMMAND GUIDE
/forget Reference key — Propose deleting a saved fact
/remember Reference key | New value — Create or update an approved fact
/plan followed by 1–5 write commands on separate lines — Atomic, approved plan
/projects — List projects
/project add Research roadmap | Compare local AI options
/search roadmap — Search facts, projects, notes and conversation history
/brief — Today's OSIS overview
/tasks — List tasks
/events — List events
/notes — List meeting notes
/memory — List saved memory
/audit — Review recent actions
/task add Prepare assembly | OSIS Deputy | 2026-11-20 | high
/task done 1
/task doing 1
/task todo 1
/task assign 1 | OSIS Deputy
/event add OSIS meeting | 2026-11-21 | 14:00 | Library | Discuss budget
/note add Meeting 1 | We agreed on the event concept
/remember Teacher's Day theme | Enter agreed theme here

All writes require your approval. Nothing is sent to students or staff. With no AI key, use these commands; with a key, you can also talk naturally."""
