"""The complete model-facing tool registry; no dynamic tool loading."""

from .validation import ACTIONS


def tool(name: str, description: str, properties: dict[str, str | dict]) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                k: (
                    v
                    if isinstance(v, dict)
                    else {
                        "type": v,
                        "description": (
                            "YYYY-MM-DD or empty string"
                            if k == "due_date"
                            else (
                                "Use empty string for unspecified optional fields"
                                if k in ("time", "location", "details")
                                else k
                            )
                        ),
                    }
                )
                for k, v in properties.items()
            },
            "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOLS = [
    tool(
        "create_project",
        "Propose saving a project record",
        {"title": "string", "goal": "string"},
    ),
    tool(
        "create_task",
        "Propose creating a task",
        {
            "title": "string",
            "owner": "string",
            "due_date": "string",
            "priority": "string",
        },
    ),
    tool(
        "set_task_status",
        "Propose marking a task todo, doing or done",
        {"task_id": "integer", "status": "string"},
    ),
    tool(
        "assign_task",
        "Propose changing the responsible person for a task",
        {"task_id": "integer", "owner": "string"},
    ),
    tool(
        "create_event",
        "Propose creating a local event",
        {
            "title": "string",
            "day": "string",
            "time": "string",
            "location": "string",
            "details": "string",
        },
    ),
    tool(
        "create_note",
        "Propose saving a meeting note",
        {"title": "string", "body": "string"},
    ),
    tool(
        "remember",
        "Propose recording a non-sensitive workspace preference or fact",
        {"key": "string", "value": "string"},
    ),
]

TOOLS.extend(
    [
        tool("forget", "Propose deleting a saved fact", {"key": "string"}),
        {
            "type": "function",
            "name": "execute_plan",
            "description": "Propose 1 to 5 local actions as an atomic plan; never executes before human approval. Each arguments_json follows that action's schema.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "enum": sorted(ACTIONS - {"execute_plan"}),
                                },
                                "arguments_json": {"type": "string"},
                            },
                            "required": ["name", "arguments_json"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["steps"],
                "additionalProperties": False,
            },
        },
    ]
)

NULLABLE_ID = {"type": ["integer", "null"], "minimum": 1}
TOOLS.extend(
    [
        tool(
            "update_project",
            "Propose updating or archiving a project",
            {
                "project_id": "integer",
                "title": "string",
                "goal": "string",
                "status": "string",
                "owner": "string",
                "target_date": "string",
            },
        ),
        tool(
            "create_milestone",
            "Propose a milestone for an existing project",
            {"project_id": "integer", "title": "string", "target_date": "string"},
        ),
        tool(
            "set_milestone_status",
            "Propose milestone status planned or done",
            {"milestone_id": "integer", "status": "string"},
        ),
        tool(
            "update_task",
            "Propose task details and explicit project/milestone links",
            {
                "task_id": "integer",
                "title": "string",
                "owner": "string",
                "due_date": "string",
                "priority": "string",
                "description": "string",
                "project_id": NULLABLE_ID,
                "milestone_id": NULLABLE_ID,
                "follow_up_context": "string",
            },
        ),
        tool(
            "add_dependency",
            "Propose an acyclic task prerequisite",
            {"task_id": "integer", "depends_on": "integer"},
        ),
        tool(
            "create_meeting",
            "Propose a meeting record; minutes remain drafts",
            {
                "title": "string",
                "held_on": "string",
                "project_id": NULLABLE_ID,
                "agenda": "string",
                "draft_minutes": "string",
                "participants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 30,
                },
            },
        ),
        tool(
            "record_decision",
            "Propose saving a decision draft; approval is separate",
            {
                "meeting_id": NULLABLE_ID,
                "project_id": NULLABLE_ID,
                "title": "string",
                "body": "string",
                "source_ref": "string",
            },
        ),
        tool(
            "approve_decision",
            "Propose confirming an existing decision draft",
            {"decision_id": "integer"},
        ),
        tool(
            "record_meeting_action",
            "Propose a draft follow-up from recorded meeting information",
            {
                "meeting_id": "integer",
                "title": "string",
                "owner": "string",
                "due_date": "string",
                "priority": "string",
            },
        ),
        tool(
            "confirm_meeting_action",
            "Propose confirming an existing meeting action draft",
            {"action_item_id": "integer"},
        ),
        tool(
            "create_followup_task",
            "Propose a task from a confirmed unconverted meeting action",
            {"action_item_id": "integer"},
        ),
    ]
)


def object_schema(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


TOOLS.append(
    tool(
        "create_project_plan",
        "Propose an atomic project with 0–5 milestones and 1–20 tasks. Task dependencies are distinct earlier task numbers (1-based). Nothing executes until approved.",
        {
            "title": "string",
            "goal": "string",
            "owner": "string",
            "target_date": "string",
            "milestones": {
                "type": "array",
                "maxItems": 5,
                "items": object_schema(
                    {"title": {"type": "string"}, "target_date": {"type": "string"}}
                ),
            },
            "tasks": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": object_schema(
                    {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "owner": {"type": "string"},
                        "due_date": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "milestone_number": NULLABLE_ID,
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "integer", "minimum": 1},
                            "maxItems": 20,
                        },
                    }
                ),
            },
        },
    )
)

assert {item["name"] for item in TOOLS} == ACTIONS
