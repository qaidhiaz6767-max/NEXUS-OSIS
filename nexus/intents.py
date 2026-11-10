"""Small bilingual deterministic intents; complex interpretation belongs to a provider."""

import re
from .briefing import build_briefing


def normalized(message):
    return (
        re.sub(r"^\s*nexus[,:]?\s+", "", message.strip(), flags=re.I)
        .strip()
        .rstrip("?!")
        .strip()
    )


def classify(message):
    raw = normalized(message)
    lower = raw.casefold()
    if raw.startswith("/"):
        return "local_command"
    if lower in {
        "status report",
        "morning briefing",
        "briefing",
        "what is going on today",
        "what's going on today",
        "whats going on today",
        "apa kabar hari ini",
        "ada apa hari ini",
        "ringkasan hari ini",
        "laporan hari ini",
    }:
        return "briefing"
    if "belum selesai" in lower or lower in {
        "unfinished tasks",
        "open tasks",
        "what needs to be done",
    }:
        return "unfinished"
    if (
        "finished this week" in lower
        or "completed this week" in lower
        or "selesai minggu ini" in lower
    ):
        return "weekly"
    if "previous decisions" in lower or "keputusan sebelumnya" in lower:
        return "decisions"
    if lower in {
        "mark it done",
        "complete that task",
        "selesaikan tugas itu",
        "tandai tugas itu selesai",
    }:
        return "resolve_task"
    if re.fullmatch(
        r"(?:mark task|complete task|selesaikan tugas)\s+\d+(?:\s+done)?", lower
    ):
        return "complete_task"
    if re.fullmatch(r"what should .+ prioritize", lower):
        return "owner_priorities"
    if ("last meeting" in lower or "rapat terakhir" in lower) and (
        "follow" in lower
        or "tindak lanjut" in lower
        or "summar" in lower
        or "ringkas" in lower
    ):
        return "meeting_followups"
    if lower in {
        "organize tomorrow's meeting",
        "organize tomorrows meeting",
        "atur rapat besok",
    }:
        return "meeting_clarification"
    return "model_or_unavailable"


def handle(store, message, intent):
    if intent in {"briefing", "unfinished", "weekly", "owner_priorities"}:
        owner = ""
        if intent == "owner_priorities":
            owner = re.fullmatch(
                r"what should (.+) prioritize", normalized(message), flags=re.I
            ).group(1)
        report = build_briefing(
            store,
            (
                "week"
                if intent == "weekly"
                else "unfinished" if intent == "unfinished" else "today"
            ),
            owner,
        )
        return {
            "message": report["message"],
            "kind": "verified_information",
            "authority_level": 0,
            "evidence": report,
        }
    if intent == "decisions":
        with store._conn() as con:
            rows = store._rows(
                con,
                "SELECT id,title,body,approved_at,source_ref FROM decisions WHERE status='approved' ORDER BY id DESC LIMIT 20",
            )
        text = "APPROVED DECISIONS\n" + (
            "\n".join(f"#{row['id']} {row['title']}: {row['body']}" for row in rows)
            or "No approved decision records are available. Draft minutes are not an approved decision register."
        )
        return {
            "message": text,
            "kind": "verified_information",
            "authority_level": 0,
            "evidence": {"workspace": store.workspace_id, "approved_decisions": rows},
        }
    if intent in {"resolve_task", "complete_task"}:
        if intent == "complete_task":
            task_id = int(re.search(r"\d+", normalized(message)).group())
        else:
            with store._conn() as con:
                ref = con.execute(
                    "SELECT last_task_id FROM conversation_references WHERE singleton=1"
                ).fetchone()
                task_id = ref[0] if ref else None
                if task_id is None:
                    rows = con.execute(
                        "SELECT id FROM tasks WHERE status!='done' LIMIT 2"
                    ).fetchall()
                    if len(rows) == 1:
                        task_id = rows[0][0]
            if task_id is None:
                return {
                    "message": "Which task should I complete? Include its task ID so the proposal refers to the right record.",
                    "kind": "clarification",
                    "authority_level": 1,
                }
        item = store.propose("set_task_status", {"task_id": task_id, "status": "done"})
        return {
            "message": f"Task #{task_id} is ready for your review. Its status has not changed.",
            "pending": item,
            "kind": "pending_approval",
            "authority_level": 2,
        }
    if intent == "meeting_clarification":
        return {
            "message": "I can prepare the meeting record and agenda. What is the meeting subject and local time? No meeting has been scheduled.",
            "kind": "clarification",
            "authority_level": 1,
        }
    if intent == "meeting_followups":
        with store._conn() as con:
            meeting = con.execute(
                "SELECT * FROM meetings ORDER BY held_on DESC,id DESC LIMIT 1"
            ).fetchone()
            if meeting is None:
                return {
                    "message": "No structured meeting record is available yet. Save a meeting record first; existing free-text notes are not automatically treated as confirmed decisions.",
                    "kind": "unavailable",
                    "authority_level": 0,
                }
            meeting = dict(meeting)
            decisions = store._rows(
                con,
                "SELECT id,title,body FROM decisions WHERE meeting_id=? AND status='approved' ORDER BY id",
                (meeting["id"],),
            )
            items = store._rows(
                con,
                "SELECT id,title FROM meeting_actions WHERE meeting_id=? AND status='confirmed' AND task_id IS NULL ORDER BY id LIMIT 5",
                (meeting["id"],),
            )
        text = f"Meeting #{meeting['id']}: {meeting['title']}\nRecorded agenda: {meeting['agenda'] or 'not set'}\nDraft minutes (not verified decisions): {meeting['draft_minutes'] or 'not recorded'}\nApproved decision records: {len(decisions)}."
        result = {
            "message": text,
            "kind": "verified_information",
            "authority_level": 0,
            "evidence": {
                "workspace": store.workspace_id,
                "meeting_id": meeting["id"],
                "approved_decisions": decisions,
            },
        }
        if items:
            result["pending"] = store.propose(
                "execute_plan",
                {
                    "steps": [
                        {
                            "name": "create_followup_task",
                            "args": {"action_item_id": item["id"]},
                        }
                        for item in items
                    ]
                },
            )
            result.update(
                kind="pending_approval",
                authority_level=2,
                message=text
                + "\nConfirmed action items are proposed as follow-up tasks. Review before approving; none have been created yet.",
            )
        else:
            result[
                "message"
            ] += "\nThere are no confirmed, unconverted follow-up items. Draft action items must be reviewed first."
        return result
    return None
